from src.models import Question, QuestionType

# TODO: Phase 1 — implement vector search over Question corpus


def retrieve(
    query: str,
    question_type: QuestionType | None = None,
    k: int = 5,
) -> list[Question]:
    raise NotImplementedError
