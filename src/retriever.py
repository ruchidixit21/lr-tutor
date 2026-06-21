import json

from src.db import get_collection
from src.models import Question, QuestionType


def retrieve(
    query: str,
    question_type: QuestionType | None = None,
    k: int = 5,
) -> list[Question]:
    """Query the Chroma collection by semantic similarity.

    Embeds `query` with the same default embedding function used at load time
    (all-MiniLM-L6-v2 via onnxruntime). Optionally filters by question_type
    using Chroma's metadata `where` clause before ranking.
    """
    collection = get_collection()

    where = {"question_type": {"$eq": question_type.value}} if question_type else None

    results = collection.query(
        query_texts=[query],
        n_results=min(k, collection.count() or 1),
        where=where,
    )

    questions: list[Question] = []
    for meta in (results["metadatas"] or [[]])[0]:
        try:
            q = Question.model_validate(json.loads(meta["question_json"]))
            questions.append(q)
        except Exception:
            continue

    return questions
