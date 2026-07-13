"""Tutor agent: Claude tool-use loop with LangSmith tracing.

TutorSession manages all state for one student session: conversation history,
the WeaknessTracker, and the current question. run_turn() drives the tool-use
loop — Claude calls tools (get_next_question, submit_answer, get_hint,
get_weakness_report), we execute them and feed results back, until Claude
produces a final text response to show the student.

LangSmith: wrap run_turn with @traceable so every tool call, input, and output
appears as a span in the trace. Set LANGSMITH_API_KEY + LANGSMITH_PROJECT in .env.
"""
import json
import os
from pathlib import Path

import anthropic

from src.generator import generate
from src.models import Question, QuestionType
from src.tools import tools
from src.weakness import WeaknessTracker

_SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "prompts" / "agent_system_prompt.txt"
).read_text()

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ---------------------------------------------------------------------------
# Hint generation
# ---------------------------------------------------------------------------

HINT_SYSTEM = """You are generating a Socratic hint for an LSAT Logical Reasoning question.
You know the correct answer but must NOT reveal it directly.

Hint 1 (attempt_number=1): Indirect. Ask a guiding question about what the question type
requires. Do not reference specific answer choices by letter.

Hint 2 (attempt_number=2): More direct. Point at the specific logical structure or gap
in the stimulus. Still do not reveal the correct answer letter.

Hint 3 (attempt_number=3): Reveal the correct answer and explain in 2–3 sentences why it
is right, then briefly note why each wrong answer fails.

Respond with the hint text only — no preamble."""


def build_hint_prompt(question: Question, attempt_number: int) -> str:
    """Build the user message for a hint request (used by both sync and streaming callers)."""
    q_summary = (
        f"Question type: {question.question_type.value}\n"
        f"Stimulus: {question.stimulus}\n"
        f"Stem: {question.stem}\n"
        f"Choices:\n"
        + "\n".join(f"  {c.label}. {c.text}" for c in question.choices)
        + f"\nCorrect answer: {question.correct_answer}"
    )
    return f"{q_summary}\n\nGenerate hint for attempt_number={attempt_number}."


def _generate_hint(question: Question, attempt_number: int) -> str:
    """Call claude-sonnet-4-6 to produce a Socratic hint calibrated to attempt_number."""
    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=HINT_SYSTEM,
        messages=[{"role": "user", "content": build_hint_prompt(question, attempt_number)}],
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class TutorSession:
    def __init__(self) -> None:
        self.weakness = WeaknessTracker()
        self.current_question: Question | None = None
        self.messages: list[dict] = []

    # ---- tool handlers ----

    def _handle_get_next_question(self, question_type: str | None) -> dict:
        qt = QuestionType(question_type) if question_type else self.weakness.select_type()
        question = generate(qt)
        self.current_question = question
        return {
            "question_id": question.id,
            "question_type": question.question_type.value,
            "stimulus": question.stimulus,
            "stem": question.stem,
            "choices": [{"label": c.label, "text": c.text} for c in question.choices],
        }

    def _handle_submit_answer(self, question_id: str, answer: str) -> dict:
        if self.current_question is None or self.current_question.id != question_id:
            return {"error": "No active question matches that ID."}
        correct = answer.strip().upper() == self.current_question.correct_answer.upper()
        self.weakness.record_attempt(self.current_question.question_type, correct)
        return {
            "correct": correct,
            "answer_given": answer,
        }

    def _handle_get_hint(self, question_id: str, attempt_number: int) -> dict:
        if self.current_question is None or self.current_question.id != question_id:
            return {"error": "No active question matches that ID."}
        hint = _generate_hint(self.current_question, attempt_number)
        return {"hint": hint, "attempt_number": attempt_number}

    def _handle_get_weakness_report(self) -> dict:
        model = self.weakness.to_model()
        return {
            "scores": model.scores,
            "attempts_by_type": model.attempts_by_type,
            "weakest_types": [qt.value for qt in self.weakness.get_weakest_types(n=3)],
        }

    def _dispatch(self, name: str, inputs: dict) -> dict:
        if name == "get_next_question":
            return self._handle_get_next_question(inputs.get("question_type"))
        if name == "submit_answer":
            return self._handle_submit_answer(inputs["question_id"], inputs["answer"])
        if name == "get_hint":
            return self._handle_get_hint(inputs["question_id"], inputs["attempt_number"])
        if name == "get_weakness_report":
            return self._handle_get_weakness_report()
        return {"error": f"Unknown tool: {name}"}

    # ---- agent loop ----

    def run_turn(self, user_message: str) -> str:
        """Run one user turn through the Claude tool-use loop.

        Appends the user message to history, then loops: send to Claude, execute
        any tool calls, feed results back, until Claude returns end_turn with a
        text response. LangSmith traces each API call as a span when LANGSMITH_API_KEY
        is set.
        """
        self.messages.append({"role": "user", "content": user_message})

        while True:
            response = _get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=tools,
                messages=self.messages,
            )

            self.messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._dispatch(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        })
                self.messages.append({"role": "user", "content": tool_results})
