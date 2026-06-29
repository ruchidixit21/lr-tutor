"""Gated generator: generate N candidates, score each, return best.

If the best candidate scores below the quality floor, regenerate up to
MAX_RETRIES times before giving up and returning whatever best was found.
This is the core generate→self-critique→select agentic pattern that
differentiates the system from naive single-shot generation.
"""
import logging

from src.generator import generate
from src.models import Question, QuestionType, RubricScore
from src.scorer import score

logger = logging.getLogger(__name__)

_CANDIDATES = 5
_QUALITY_FLOOR = 3.5
_MAX_RETRIES = 2


def generate_gated(
    question_type: QuestionType,
    candidates: int = _CANDIDATES,
    quality_floor: float = _QUALITY_FLOOR,
    max_retries: int = _MAX_RETRIES,
) -> tuple[Question, RubricScore]:
    """Generate N candidates, score each, return the highest-scoring one.

    Generates N questions sequentially, scores each with the rubric scorer,
    and returns the best. If the best average is below quality_floor, retries
    the full slate up to max_retries times. Returns the best seen across all
    attempts regardless of whether the floor was met, so callers always get
    something. Raises RuntimeError only if every API call fails.

    Returns (question, score) so callers can log or display the rubric.
    """
    best_question: Question | None = None
    best_score: RubricScore | None = None

    for attempt in range(1 + max_retries):
        slate: list[tuple[Question, RubricScore]] = []

        for i in range(candidates):
            try:
                q = generate(question_type)
                s = score(q)
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

    return best_question, best_score
