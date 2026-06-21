from fastapi import FastAPI, HTTPException, Query

from src.models import Question, QuestionType
from src.retriever import retrieve

app = FastAPI(title="LSAT Tutor API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/retrieve", response_model=list[Question])
def retrieve_questions(
    type: QuestionType | None = Query(default=None, description="Filter by question type"),
    k: int = Query(default=5, ge=1, le=20, description="Number of results"),
    q: str = Query(description="Query text describing the reasoning structure to retrieve"),
) -> list[Question]:
    """Return the k most similar Questions from the corpus.

    Retrieval is by semantic similarity of (stimulus + stem) embeddings.
    Optionally filters to a specific question type before ranking.
    """
    try:
        return retrieve(query=q, question_type=type, k=k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# TODO: Phase 2 — POST /generate, POST /score
# TODO: Phase 3 — POST /session, POST /session/{id}/answer, GET /session/{id}/hint
