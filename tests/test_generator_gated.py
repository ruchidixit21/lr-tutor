"""Tests for the gated generator.

Mocks generate() and score() to verify: best-selection logic, retry on
low score, early exit when floor is met, and RuntimeError on total failure.
"""
from unittest.mock import MagicMock, call, patch

import pytest

from src.generator_gated import generate_gated
from src.models import AnswerChoice, Question, QuestionSource, QuestionType, RubricScore


def _make_question(qid: str = "q1") -> Question:
    return Question(
        id=qid,
        question_type=QuestionType.WEAKEN,
        stimulus="Test stimulus.",
        stem="Which weakens?",
        choices=[
            AnswerChoice(label="A", text="a"),
            AnswerChoice(label="B", text="b"),
            AnswerChoice(label="C", text="c"),
            AnswerChoice(label="D", text="d"),
            AnswerChoice(label="E", text="e"),
        ],
        correct_answer="A",
        source=QuestionSource.GENERATED,
    )


def _make_score(avg: float, qid: str = "q1") -> RubricScore:
    v = round(avg)
    v = max(1, min(5, v))
    return RubricScore(
        question_id=qid,
        logical_validity=v,
        answer_uniqueness=v,
        distractor_quality=v,
        type_accuracy=v,
        stimulus_independence=v,
    )


@patch("src.generator_gated.score")
@patch("src.generator_gated.generate")
def test_returns_best_candidate(mock_gen, mock_score):
    """Should return the highest-scoring candidate from the first slate."""
    q_low = _make_question("low")
    q_high = _make_question("high")

    # generate called 5 times; alternate low/high
    mock_gen.side_effect = [q_low, q_high, q_low, q_low, q_low]
    mock_score.side_effect = [
        _make_score(3.0, "low"),
        _make_score(4.0, "high"),
        _make_score(3.0, "low"),
        _make_score(3.0, "low"),
        _make_score(3.0, "low"),
    ]

    q, s = generate_gated(QuestionType.WEAKEN, candidates=5, quality_floor=3.5, max_retries=0)
    assert q.id == "high"
    assert s.average == 4.0


@patch("src.generator_gated.score")
@patch("src.generator_gated.generate")
def test_retries_when_below_floor(mock_gen, mock_score):
    """Should retry when best of first slate is below quality_floor."""
    q_bad = _make_question("bad")
    q_good = _make_question("good")

    # First 2 candidates below floor, then 2 good ones on retry
    mock_gen.side_effect = [q_bad, q_bad, q_good, q_good]
    mock_score.side_effect = [
        _make_score(2.0, "bad"),
        _make_score(2.0, "bad"),
        _make_score(4.0, "good"),
        _make_score(4.0, "good"),
    ]

    q, s = generate_gated(QuestionType.WEAKEN, candidates=2, quality_floor=3.5, max_retries=1)
    assert q.id == "good"
    assert s.average == 4.0
    assert mock_gen.call_count == 4


@patch("src.generator_gated.score")
@patch("src.generator_gated.generate")
def test_exits_early_when_floor_met(mock_gen, mock_score):
    """Should not retry when first slate already meets the floor."""
    q = _make_question("ok")
    mock_gen.return_value = q
    mock_score.return_value = _make_score(4.0, "ok")

    result_q, result_s = generate_gated(QuestionType.WEAKEN, candidates=3, quality_floor=3.5, max_retries=2)
    assert mock_gen.call_count == 3  # only one slate, no retries


@patch("src.generator_gated.score")
@patch("src.generator_gated.generate")
def test_raises_when_all_fail(mock_gen, mock_score):
    """Should raise RuntimeError if generate() always throws."""
    mock_gen.side_effect = RuntimeError("API down")

    with pytest.raises(RuntimeError, match="All generation attempts failed"):
        generate_gated(QuestionType.WEAKEN, candidates=2, quality_floor=3.5, max_retries=0)
