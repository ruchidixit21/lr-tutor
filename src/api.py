from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.generator import generate
from src.models import Question, QuestionType, RubricScore
from src.retriever import retrieve
from src.scorer import score

app = FastAPI(title="LSAT Tutor API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/retrieve", response_model=list[Question])
def retrieve_questions(
    q: str = Query(description="Query text describing the reasoning structure to retrieve"),
    type: QuestionType | None = Query(default=None, description="Filter by question type"),
    k: int = Query(default=5, ge=1, le=20),
) -> list[Question]:
    """Return the k most semantically similar Questions from the corpus."""
    try:
        return retrieve(query=q, question_type=type, k=k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerateRequest(BaseModel):
    question_type: QuestionType
    k: int = 3  # number of RAG examples to retrieve


@app.post("/generate", response_model=Question)
def generate_question(req: GenerateRequest) -> Question:
    """Generate one RAG-grounded question of the requested type."""
    try:
        return generate(question_type=req.question_type, k=req.k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/score", response_model=RubricScore)
def score_question(question: Question) -> RubricScore:
    """Score a Question on the five rubric dimensions."""
    try:
        return score(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# TODO: Phase 3 — POST /session, POST /session/{id}/answer, GET /session/{id}/hint
