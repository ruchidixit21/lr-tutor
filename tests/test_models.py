import pytest
from src.models import (
    AnswerChoice,
    Question,
    QuestionSource,
    QuestionType,
    RubricScore,
    SessionAttempt,
    WeaknessModel,
)


@pytest.fixture
def sample_question() -> Question:
    return Question(
        question_type=QuestionType.WEAKEN,
        stimulus="All mammals are warm-blooded. Whales are mammals. Therefore, whales are warm-blooded.",
        stem="Which of the following, if true, most weakens the argument above?",
        choices=[
            AnswerChoice(label="A", text="Some fish are also warm-blooded."),
            AnswerChoice(label="B", text="Whales live in cold ocean water."),
            AnswerChoice(label="C", text="The definition of 'mammal' is disputed by some biologists."),
            AnswerChoice(label="D", text="Warm-blooded animals regulate their body temperature internally."),
            AnswerChoice(label="E", text="Whales breathe air rather than extracting oxygen from water."),
        ],
        correct_answer="C",
        source=QuestionSource.GENERATED,
    )


def test_question_has_id(sample_question):
    assert sample_question.id is not None
    assert len(sample_question.id) > 0


def test_question_roundtrip_json(sample_question):
    data = sample_question.model_dump()
    restored = Question.model_validate(data)
    assert restored.id == sample_question.id
    assert restored.question_type == QuestionType.WEAKEN
    assert len(restored.choices) == 5


def test_rubric_score_average():
    score = RubricScore(
        question_id="test-id",
        logical_validity=4,
        answer_uniqueness=5,
        distractor_quality=3,
        type_accuracy=4,
        stimulus_independence=4,
    )
    assert score.average == 4.0


def test_weakness_model_structure():
    model = WeaknessModel(
        scores={qt.value: 0.5 for qt in QuestionType},
        attempts_by_type={qt.value: 0 for qt in QuestionType},
    )
    assert len(model.scores) == 15
    assert all(0.0 <= v <= 1.0 for v in model.scores.values())
