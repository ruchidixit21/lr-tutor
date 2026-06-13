from src.models import QuestionType, WeaknessModel

# TODO: Phase 3 — per-type rolling accuracy with exponential decay


class WeaknessTracker:
    def record_attempt(self, question_type: QuestionType, correct: bool) -> None:
        raise NotImplementedError

    def get_weakest_types(self, n: int = 3) -> list[QuestionType]:
        raise NotImplementedError

    def to_model(self) -> WeaknessModel:
        raise NotImplementedError
