"""Tests for TutorSession tool dispatch logic.

These tests mock the Anthropic client and generator so they run fast and offline.
They verify that: tool dispatch routes correctly, submit_answer records to the
WeaknessTracker, and get_hint is gated on current_question state.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.agent import TutorSession
from src.models import AnswerChoice, Question, QuestionSource, QuestionType


@pytest.fixture
def sample_question() -> Question:
    return Question(
        question_type=QuestionType.WEAKEN,
        stimulus="All mammals are warm-blooded. Whales are mammals.",
        stem="Which of the following, if true, most seriously weakens the argument?",
        choices=[
            AnswerChoice(label="A", text="Some fish are warm-blooded."),
            AnswerChoice(label="B", text="Whales live in cold water."),
            AnswerChoice(label="C", text="Not all warm-blooded animals are mammals."),
            AnswerChoice(label="D", text="Whales breathe air."),
            AnswerChoice(label="E", text="Some mammals are not warm-blooded."),
        ],
        correct_answer="E",
        source=QuestionSource.GENERATED,
    )


def test_submit_answer_correct(sample_question):
    session = TutorSession()
    session.current_question = sample_question
    result = session._handle_submit_answer(sample_question.id, "E")
    assert result["correct"] is True
    assert session.weakness._attempts[QuestionType.WEAKEN.value] == [True]


def test_submit_answer_wrong(sample_question):
    session = TutorSession()
    session.current_question = sample_question
    result = session._handle_submit_answer(sample_question.id, "B")
    assert result["correct"] is False
    assert session.weakness._attempts[QuestionType.WEAKEN.value] == [False]


def test_submit_answer_wrong_question_id(sample_question):
    session = TutorSession()
    session.current_question = sample_question
    result = session._handle_submit_answer("nonexistent-id", "A")
    assert "error" in result


def test_get_hint_no_question():
    session = TutorSession()
    result = session._handle_get_hint("any-id", 1)
    assert "error" in result


def test_get_weakness_report_initial():
    session = TutorSession()
    result = session._handle_get_weakness_report()
    assert "scores" in result
    assert "attempts_by_type" in result
    assert len(result["weakest_types"]) == 3
    # all unseen types score 0.5, so all attempts should be 0
    for qt_val, count in result["attempts_by_type"].items():
        assert count == 0


def test_dispatch_unknown_tool():
    session = TutorSession()
    result = session._dispatch("nonexistent_tool", {})
    assert "error" in result


@patch("src.agent.generate")
def test_get_next_question_sets_current(mock_generate, sample_question):
    mock_generate.return_value = sample_question
    session = TutorSession()
    result = session._handle_get_next_question(QuestionType.WEAKEN.value)
    assert session.current_question is sample_question
    assert result["question_id"] == sample_question.id
    assert result["question_type"] == QuestionType.WEAKEN.value
    assert len(result["choices"]) == 5
