"""Background question cache: pre-generate questions so delivery is instant.

Architecture
------------
QuestionCache maintains a pool of ready-to-serve (Question, RubricScore) pairs
per QuestionType. A background thread continuously refills any type that falls
below the target pool size by calling generate_gated (which itself parallelises
its 5 candidates internally).

On /next-question:
  1. Pop one question from the pool for the requested type (instant).
  2. If the pool is empty (cold start or burst), fall back to a direct
     generate_gated call on the request thread (student waits ~8s).
  3. The refill loop notices the pool shrank and queues a replacement.

The cache runs as a daemon thread — it dies when the server process exits,
no cleanup required.

Usage
-----
    from src.question_cache import question_cache

    question_cache.start()          # call once at server startup
    question_cache.pre_warm()       # optional: block until pool has ≥1 per type
    q, s = question_cache.get(qt)   # instant if warm, ~8s fallback if cold
"""
import logging
import threading
from collections import defaultdict

from src.generator_gated import generate_gated
from src.models import Question, QuestionType, RubricScore

logger = logging.getLogger(__name__)

# Number of pre-generated questions to keep ready per type.
# 3 per type × 15 types = 45 questions in memory (~negligible).
_TARGET_PER_TYPE = 3

# How many types to refill concurrently. Each refill call already uses 5
# threads internally (generate_gated), so keep this modest to avoid
# hammering the Anthropic API with too many parallel requests.
_REFILL_CONCURRENCY = 3


class QuestionCache:
    def __init__(self, target: int = _TARGET_PER_TYPE) -> None:
        self._target = target
        # pool[type] = list of (Question, RubricScore) ready to serve
        self._pool: dict[QuestionType, list[tuple[Question, RubricScore]]] = defaultdict(list)
        self._lock = threading.Lock()
        # Semaphore limits concurrent refill workers
        self._refill_sem = threading.Semaphore(_REFILL_CONCURRENCY)
        self._started = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background refill loop. Safe to call multiple times."""
        if self._started:
            return
        self._started = True
        t = threading.Thread(target=self._refill_loop, daemon=True, name="question-cache-refill")
        t.start()
        logger.info("Question cache started (target=%d per type)", self._target)

    def pre_warm(self) -> None:
        """Block until every question type has at least one question ready.

        Call this at server startup (inside the lifespan context) to ensure
        the first student request is served from cache. Takes ~8s if the
        cache is cold (one parallel generate_gated per type, up to
        _REFILL_CONCURRENCY at a time).
        """
        types_needed = list(QuestionType)
        done = threading.Event()
        remaining = [len(types_needed)]
        lock = threading.Lock()

        def refill_one(qt: QuestionType) -> None:
            with self._refill_sem:
                try:
                    q, s = generate_gated(qt)
                    with self._lock:
                        self._pool[qt].append((q, s))
                    logger.info("pre-warm: %s ready (avg=%.2f)", qt.value, s.average)
                except Exception:
                    logger.exception("pre-warm failed for %s", qt.value)
                finally:
                    with lock:
                        remaining[0] -= 1
                        if remaining[0] == 0:
                            done.set()

        threads = [
            threading.Thread(target=refill_one, args=(qt,), daemon=True)
            for qt in types_needed
        ]
        for t in threads:
            t.start()
        done.wait()
        logger.info("pre-warm complete — all %d types have ≥1 question ready", len(types_needed))

    def get(self, question_type: QuestionType) -> tuple[Question, RubricScore]:
        """Return a question for the given type.

        Pops from the pre-generated pool if available (instant). Falls back
        to a direct generate_gated call if the pool is empty (cold start or
        brief burst). The background loop will replenish the pool afterwards.
        """
        with self._lock:
            pool = self._pool[question_type]
            if pool:
                result = pool.pop()
                logger.debug("cache hit: %s (%d remaining)", question_type.value, len(pool))
                return result

        # Cache miss — generate synchronously so the student isn't blocked forever
        logger.warning("cache miss for %s — generating synchronously", question_type.value)
        return generate_gated(question_type)

    def pool_sizes(self) -> dict[str, int]:
        """Return current pool depth per type — useful for monitoring."""
        with self._lock:
            return {qt.value: len(self._pool[qt]) for qt in QuestionType}

    # ------------------------------------------------------------------
    # Background refill loop
    # ------------------------------------------------------------------

    def _needs_refill(self) -> list[QuestionType]:
        """Return types whose pool is below target, sorted most-depleted first."""
        with self._lock:
            return sorted(
                [qt for qt in QuestionType if len(self._pool[qt]) < self._target],
                key=lambda qt: len(self._pool[qt]),
            )

    def _refill_one(self, qt: QuestionType) -> None:
        """Generate one question and add it to the pool. Respects the semaphore."""
        with self._refill_sem:
            try:
                q, s = generate_gated(qt)
                with self._lock:
                    self._pool[qt].append((q, s))
                logger.info(
                    "cache refill: %s avg=%.2f (pool now %d)",
                    qt.value, s.average, len(self._pool[qt]),
                )
            except Exception:
                logger.exception("cache refill failed for %s", qt.value)

    def _refill_loop(self) -> None:
        """Daemon loop: whenever a type is below target, spawn a refill thread."""
        while True:
            needed = self._needs_refill()
            if needed:
                # Launch one refill thread per depleted type; semaphore caps concurrency
                threads = [
                    threading.Thread(target=self._refill_one, args=(qt,), daemon=True)
                    for qt in needed
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
            else:
                # Pool is full — check again in 10s
                threading.Event().wait(timeout=10)


# Module-level singleton — import this everywhere
question_cache = QuestionCache()
