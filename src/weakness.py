import random

from src.models import QuestionType, WeaknessModel


class WeaknessTracker:
    """Per-type accuracy tracker with exponential recency decay.

    Each attempt is weighted by decay^age (age=0 is most recent). Attempts within
    the last 10 get an additional 2x boost per the spec. Unseen types start at 0.5
    (neutral prior) so the agent explores all types before exploiting known weaknesses.
    """

    def __init__(self, decay: float = 0.85):
        self._decay = decay
        self._attempts: dict[str, list[bool]] = {qt.value: [] for qt in QuestionType}

    def record_attempt(self, question_type: QuestionType, correct: bool) -> None:
        self._attempts[question_type.value].append(correct)

    def _score(self, attempts: list[bool]) -> float:
        if not attempts:
            return 0.5
        n = len(attempts)
        weighted_correct = 0.0
        weighted_total = 0.0
        for i, correct in enumerate(attempts):
            age = n - 1 - i  # 0 = most recent
            w = self._decay ** age
            if age < 10:  # last 10 attempts count double
                w *= 2
            weighted_total += w
            if correct:
                weighted_correct += w
        return weighted_correct / weighted_total

    def get_weakest_types(self, n: int = 3) -> list[QuestionType]:
        scores = {qt: self._score(self._attempts[qt.value]) for qt in QuestionType}
        return sorted(scores, key=lambda qt: scores[qt])[:n]

    def select_type(self) -> QuestionType:
        """Sample a question type weighted toward weaker types.

        Uses (1 - score) as the sampling weight so weaker types are chosen more
        often. A small floor (0.05) ensures every type stays reachable.
        """
        types = list(QuestionType)
        weights = [
            max(1.0 - self._score(self._attempts[qt.value]), 0.05)
            for qt in types
        ]
        return random.choices(types, weights=weights, k=1)[0]

    def to_model(self) -> WeaknessModel:
        return WeaknessModel(
            scores={qt.value: self._score(self._attempts[qt.value]) for qt in QuestionType},
            attempts_by_type={qt.value: len(self._attempts[qt.value]) for qt in QuestionType},
        )
