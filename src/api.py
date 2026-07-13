import json
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()
from pydantic import BaseModel

from src.agent import HINT_SYSTEM, TutorSession, build_hint_prompt
from src.generator import generate
from src.models import Question, QuestionType, RubricScore
from src.retriever import retrieve
from src.scorer import score

_HUMAN_SCORES_PATH = Path("eval/human_scores.jsonl")

app = FastAPI(title="LSAT Tutor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class ChoiceData(BaseModel):
    label: str
    text: str


class QuestionData(BaseModel):
    question_id: str
    question_type: str
    stimulus: str
    stem: str
    choices: list[ChoiceData]


class SessionResponse(BaseModel):
    session_id: str
    message: str
    question: QuestionData | None = None
    weakness_scores: dict[str, float] | None = None


class MessageRequest(BaseModel):
    message: str


def _build_response(session_id: str, session: TutorSession, message: str) -> SessionResponse:
    """Attach current question and weakness scores to every session response."""
    question = None
    if session.current_question:
        q = session.current_question
        question = QuestionData(
            question_id=q.id,
            question_type=q.question_type.value,
            stimulus=q.stimulus,
            stem=q.stem,
            choices=[ChoiceData(label=c.label, text=c.text) for c in q.choices],
        )
    weakness = session.weakness.to_model()
    return SessionResponse(
        session_id=session_id,
        message=message,
        question=question,
        weakness_scores=weakness.scores,
    )


@app.post("/session", response_model=SessionResponse)
def create_session() -> SessionResponse:
    """Create a new tutoring session. Returns session_id and the opening message."""
    session_id = str(uuid.uuid4())
    session = TutorSession()
    opening = session.run_turn("Let's start a session. Please greet me briefly and give me my first question.")
    _sessions[session_id] = session
    return _build_response(session_id, session, opening)


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
    return _build_response(session_id, session, reply)


@app.post("/session/{session_id}/next-question", response_model=SessionResponse)
def next_question(session_id: str) -> SessionResponse:
    """Generate and return the next question directly — no agent loop.

    Uses the WeaknessTracker to select the question type, then calls generate()
    to produce a new question. Bypasses the conversational agent entirely because
    question selection is mechanical, not conversational.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    qt = session.weakness.select_type()
    try:
        question = generate(qt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    session.current_question = question
    session.messages = []  # fresh history so the agent isn't confused by the previous question
    return _build_response(session_id, session, "")


class SubmitAnswerRequest(BaseModel):
    answer: str


class SubmitAnswerResponse(BaseModel):
    correct: bool
    explanation: str | None
    weakness_scores: dict[str, float]


@app.post("/session/{session_id}/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer(session_id: str, req: SubmitAnswerRequest) -> SubmitAnswerResponse:
    """Deterministic answer check — no LLM call. Records the attempt and returns immediately."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.current_question is None:
        raise HTTPException(status_code=400, detail="No active question")
    q = session.current_question
    correct = req.answer.strip().upper() == q.correct_answer.upper()
    if q.id not in session._recorded_ids:
        session.weakness.record_attempt(q.question_type, correct)
        session._recorded_ids.add(q.id)
    return SubmitAnswerResponse(
        correct=correct,
        explanation=q.explanation,
        weakness_scores=session.weakness.to_model().scores,
    )


# ---------------------------------------------------------------------------
# Phase 5 — SSE hint streaming + human eval
# ---------------------------------------------------------------------------

@app.get("/session/{session_id}/hint-stream")
def hint_stream(
    session_id: str,
    question_id: str = Query(),
    attempt_number: int = Query(ge=1, le=3),
) -> StreamingResponse:
    """Stream a Socratic hint token-by-token via SSE."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.current_question is None or session.current_question.id != question_id:
        raise HTTPException(status_code=400, detail="Question ID does not match active question")

    question = session.current_question

    import anthropic as _anthropic

    def event_stream():
        client = _anthropic.Anthropic()
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=HINT_SYSTEM,
            messages=[{
                "role": "user",
                "content": build_hint_prompt(question, attempt_number),
            }],
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {text}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


class HumanScoreRequest(BaseModel):
    question_id: str
    logical_validity: int
    answer_uniqueness: int
    distractor_quality: int
    type_accuracy: int
    stimulus_independence: int
    notes: str = ""


@app.post("/human-score")
def submit_human_score(req: HumanScoreRequest) -> dict:
    """Append a human rubric rating to eval/human_scores.jsonl."""
    _HUMAN_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _HUMAN_SCORES_PATH.open("a") as f:
        f.write(json.dumps(req.model_dump()) + "\n")
    return {"status": "saved"}
