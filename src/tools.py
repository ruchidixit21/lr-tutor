from src.models import QuestionType

# TODO: Phase 3 — tool schemas and handlers for the agentic loop

tools = [
    {
        "name": "get_next_question",
        "description": (
            "Get the next question for the student. Selects question type based "
            "on current weakness model — weakest types get higher probability. "
            "Optionally override with a specific type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_type": {
                    "type": "string",
                    "description": "Optional. Force a specific question type.",
                    "enum": [qt.value for qt in QuestionType],
                }
            },
        },
    },
    {
        "name": "submit_answer",
        "description": (
            "Submit the student's answer to the current question. Returns whether "
            "it was correct and records the attempt in the weakness model."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "string"},
                "answer": {"type": "string", "enum": ["A", "B", "C", "D", "E"]},
            },
            "required": ["question_id", "answer"],
        },
    },
    {
        "name": "get_hint",
        "description": (
            "Get a Socratic hint for the current question. Hints guide the student "
            "toward the answer without revealing it. Hint level increases with "
            "attempt_number — first hint is very indirect, second is more direct."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "string"},
                "attempt_number": {"type": "integer", "minimum": 1, "maximum": 3},
            },
            "required": ["question_id", "attempt_number"],
        },
    },
    {
        "name": "get_weakness_report",
        "description": (
            "Get the student's current weakness profile across all question types. "
            "Returns scores 0.0-1.0 per type and total attempts."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]
