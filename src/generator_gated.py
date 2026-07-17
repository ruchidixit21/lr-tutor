"""Gated generator: generate N candidates in parallel, score each, return best.

Candidates are generated and scored concurrently using a ThreadPoolExecutor,
reducing wall-clock time from O(N) sequential API calls to O(1) — roughly
the time of a single generate+score pair regardless of candidate count.

If the best candidate scores below the quality floor, regenerate up to
MAX_RETRIES times before giving up and returning whatever best was found.
This is the core generate→self-critique→select agentic pattern that
differentiates the system from naive single-shot generation.
"""
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from src.generator import generate
from src.models import Question, QuestionType, RubricScore
from src.scorer import score

logger = logging.getLogger(__name__)

_CANDIDATES = 5
_QUALITY_FLOOR = 3.5
_MAX_RETRIES = 2


def _generate_and_score(question_type: QuestionType) -> tuple[Question, RubricScore]:
    """Generate one candidate and score it, retrying on 529 overload errors."""
    import anthropic
    for attempt in range(4):
        try:
            q = generate(question_type)
            s = score(q)
            return q, s
        except anthropic.OverloadedError:
            if attempt == 3:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning("API overloaded, retrying in %ds (attempt %d/4)", wait, attempt + 1)
            time.sleep(wait)


def _log_rubric_feedback(score: RubricScore) -> None:
    """Attach rubric scores as LangSmith feedback on the current generate_gated run."""
    if not os.getenv("LANGSMITH_API_KEY"):
        return
    try:
        from langsmith import Client
        run_tree = get_current_run_tree()
        if run_tree is None:
            return
        client = Client()
        client.create_feedback(run_tree.id, key="rubric_avg", score=score.average / 5.0)
        for dim in ("logical_validity", "answer_uniqueness", "distractor_quality",
                    "type_accuracy", "stimulus_independence"):
            client.create_feedback(run_tree.id, key=dim, score=getattr(score, dim) / 5.0)
    except Exception:
        logger.debug("LangSmith feedback logging failed", exc_info=True)


@traceable(name="generate_gated")
def generate_gated(
    question_type: QuestionType,
    candidates: int = _CANDIDATES,
    quality_floor: float = _QUALITY_FLOOR,
    max_retries: int = _MAX_RETRIES,
) -> tuple[Question, RubricScore]:
    """Generate N candidates in parallel, score each, return the highest-scoring one.

    All candidates are submitted to a ThreadPoolExecutor simultaneously so
    generate+score pairs run concurrently. Wall-clock time is roughly that of
    one API round-trip pair rather than N sequential pairs.

    If the best average is below quality_floor, retries the full slate up to
    max_retries times. Returns the best seen across all attempts regardless of
    whether the floor was met. Raises RuntimeError only if every API call fails.

    Returns (question, score) so callers can log or display the rubric.
    """
    best_question: Question | None = None
    best_score: RubricScore | None = None

    for attempt in range(1 + max_retries):
        slate: list[tuple[Question, RubricScore]] = []

        with ThreadPoolExecutor(max_workers=candidates) as pool:
            futures = {
                pool.submit(_generate_and_score, question_type): i
                for i in range(candidates)
            }
            for future in as_completed(futures):
                i = futures[future]
                try:
                    q, s = future.result()
                    slate.append((q, s))
                    logger.debug(
                        "attempt=%d candidate=%d type=%s avg=%.2f",
                        attempt, i, question_type.value, s.average,
                    )
                except Exception:
                    logger.exception("candidate %d failed on attempt %d", i, attempt)

        if not slate:
            continue

        attempt_best_q, attempt_best_s = max(slate, key=lambda t: t[1].average)

        if best_score is None or attempt_best_s.average > best_score.average:
            best_question = attempt_best_q
            best_score = attempt_best_s

        if best_score.average >= quality_floor:
            logger.info(
                "type=%s quality_floor met: avg=%.2f after %d attempt(s)",
                question_type.value, best_score.average, attempt + 1,
            )
            break

        if attempt < max_retries:
            logger.warning(
                "type=%s best avg=%.2f below floor %.2f — regenerating (attempt %d/%d)",
                question_type.value, best_score.average, quality_floor,
                attempt + 1, 1 + max_retries,
            )

    if best_question is None or best_score is None:
        raise RuntimeError(f"All generation attempts failed for type {question_type.value}")

    _log_rubric_feedback(best_score)
    return best_question, best_score
