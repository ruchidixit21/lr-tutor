import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

load_dotenv()
from pydantic import BaseModel

from src.agent import TutorSession
from src.generator import generate
from src.models import Question, QuestionType, RubricScore
from src.retriever import retrieve
from src.scorer import score

app = FastAPI(title="LSAT Tutor API")

_sessions: dict[str, TutorSession] = {}


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


# ---------------------------------------------------------------------------
# Phase 3 — session endpoints
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str
    message: str


class MessageRequest(BaseModel):
    message: str


@app.post("/session", response_model=SessionResponse)
def create_session() -> SessionResponse:
    """Create a new tutoring session. Returns session_id and the opening message."""
    session_id = str(uuid.uuid4())
    session = TutorSession()
    opening = session.run_turn("Let's start a session. Please greet me briefly and give me my first question.")
    _sessions[session_id] = session
    return SessionResponse(session_id=session_id, message=opening)


@app.post("/session/{session_id}/message", response_model=SessionResponse)
def send_message(session_id: str, req: MessageRequest) -> SessionResponse:
    """Send a user message to an active session and get the agent's response."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        reply = session.run_turn(req.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return SessionResponse(session_id=session_id, message=reply)
