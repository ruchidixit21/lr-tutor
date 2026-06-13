from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid


class QuestionType(str, Enum):
    ASSUMPTION_NECESSARY  = "assumption_necessary"
    ASSUMPTION_SUFFICIENT = "assumption_sufficient"
    STRENGTHEN            = "strengthen"
    WEAKEN                = "weaken"
    FLAW                  = "flaw"
    INFERENCE             = "inference"
    MUST_BE_TRUE          = "must_be_true"
    CANNOT_BE_TRUE        = "cannot_be_true"
    PARADOX               = "paradox"
    PARALLEL_REASONING    = "parallel_reasoning"
    PARALLEL_FLAW         = "parallel_flaw"
    POINT_OF_DISAGREEMENT = "point_of_disagreement"
    EVALUATE              = "evaluate"
    PRINCIPLE_IDENTIFY    = "principle_identify"
    PRINCIPLE_APPLY       = "principle_apply"


class QuestionSource(str, Enum):
    REAL_LSAT  = "real_lsat"
    SCRAPED    = "scraped"
    SCANNED    = "scanned"
    GENERATED  = "generated"


class AnswerChoice(BaseModel):
    label: str  # "A", "B", "C", "D", "E"
    text: str


class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_type: QuestionType
    stimulus: str
    stem: str
    choices: list[AnswerChoice]  # always exactly 5
    correct_answer: str          # "A" through "E"
    explanation: Optional[str] = None
    source: QuestionSource
    source_detail: Optional[str] = None  # e.g. "PrepTest 71, Section 2, Q14"


class RubricScore(BaseModel):
    question_id: str
    logical_validity: int        # 1-5: does the argument gap actually exist?
    answer_uniqueness: int       # 1-5: exactly one defensible correct answer?
    distractor_quality: int      # 1-5: wrong answers unambiguously wrong?
    type_accuracy: int           # 1-5: does it actually test what it claims?
    stimulus_independence: int   # 1-5: answerable without outside knowledge?
    notes: Optional[str] = None

    @property
    def average(self) -> float:
        scores = [
            self.logical_validity,
            self.answer_uniqueness,
            self.distractor_quality,
            self.type_accuracy,
            self.stimulus_independence,
        ]
        return sum(scores) / len(scores)


class SessionAttempt(BaseModel):
    question_id: str
    question_type: QuestionType
    answer_given: str
    correct: bool
    hints_used: int
    timestamp: str  # ISO 8601


class WeaknessModel(BaseModel):
    # maps QuestionType value -> score 0.0-1.0 (1.0 = strong, 0.0 = weak)
    scores: dict[str, float]
    attempts_by_type: dict[str, int]
