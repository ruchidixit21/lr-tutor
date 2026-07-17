import json
import os

import anthropic
from langsmith import traceable

from src.models import Question, QuestionSource, QuestionType
from src.retriever import retrieve

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_TYPE_INSTRUCTIONS: dict[QuestionType, str] = {
    QuestionType.ASSUMPTION_NECESSARY: (
        "The stimulus presents an argument with a logical gap. The stem asks which answer "
        "the argument REQUIRES to be true — without it, the conclusion cannot stand. "
        "The correct answer is a necessary (not merely helpful) bridge premise."
    ),
    QuestionType.ASSUMPTION_SUFFICIENT: (
        "The stimulus is an incomplete argument (often ending with a blank '______'). "
        "The stem asks which answer, if added as a premise, allows the conclusion to be "
        "properly drawn. Use a fill-in-the-blank stem format."
    ),
    QuestionType.STRENGTHEN: (
        "The stimulus presents an argument with a gap or vulnerability. The correct answer "
        "provides new information that makes the conclusion more likely to be true. "
        "Wrong answers are irrelevant, weaken, or address a different issue."
    ),
    QuestionType.WEAKEN: (
        "The stimulus presents an argument. The correct answer provides new information "
        "that makes the conclusion less likely to be true — typically by offering an "
        "alternative explanation, undermining a premise, or exposing a flaw."
    ),
    QuestionType.FLAW: (
        "The stimulus presents an argument that commits a specific logical error. The stem "
        "asks which answer describes the flaw. The correct answer names the error precisely "
        "(e.g., ad hominem, false dichotomy, correlation/causation, part-to-whole)."
    ),
    QuestionType.INFERENCE: (
        "The stimulus presents a set of facts or claims. The stem asks which answer can be "
        "properly inferred — it must be supported by the stimulus but need not be certain. "
        "Do not use 'must be true' phrasing; use 'most strongly supported' or 'can be inferred'."
    ),
    QuestionType.MUST_BE_TRUE: (
        "The stimulus presents a set of statements. The correct answer MUST follow from "
        "those statements with certainty — it cannot be false if the stimulus is true. "
        "Wrong answers might be true but are not guaranteed."
    ),
    QuestionType.CANNOT_BE_TRUE: (
        "The stimulus presents a set of statements. The correct answer is IMPOSSIBLE given "
        "those statements — it directly contradicts what the stimulus establishes. "
        "Wrong answers could be true or are simply unknown."
    ),
    QuestionType.PARADOX: (
        "The stimulus describes two facts that seem contradictory or surprising together. "
        "The correct answer, if true, explains why both facts can coexist. "
        "Wrong answers either explain only one fact, are irrelevant, or make the paradox worse."
    ),
    QuestionType.PARALLEL_REASONING: (
        "The stimulus presents an argument with a specific logical structure. The stem asks "
        "which answer argument has the SAME structure — same pattern of premises and conclusion, "
        "regardless of topic. Wrong answers use a similar but subtly different structure."
    ),
    QuestionType.PARALLEL_FLAW: (
        "The stimulus presents a flawed argument. The correct answer contains the SAME type "
        "of logical flaw, not just a similar topic. Wrong answers have different flaws or "
        "are valid arguments."
    ),
    QuestionType.POINT_OF_DISAGREEMENT: (
        "The stimulus contains a dialogue between two speakers. The stem asks what they "
        "DISAGREE about — both speakers must directly address the same claim, one affirming "
        "and one denying it. Wrong answers are things only one speaker addressed."
    ),
    QuestionType.EVALUATE: (
        "The stimulus presents an argument. The correct answer names a piece of information "
        "that would be useful to EVALUATE the argument — it could either strengthen or weaken "
        "it depending on the answer. Wrong answers are irrelevant or already settled."
    ),
    QuestionType.PRINCIPLE_IDENTIFY: (
        "The stimulus presents a specific situation or judgment. The stem asks which general "
        "principle is best illustrated by or underlies it. The correct answer is a general "
        "rule that the situation exemplifies."
    ),
    QuestionType.PRINCIPLE_APPLY: (
        "The stimulus states a general principle. The stem asks which answer situation is "
        "most consistent with or most in accord with that principle. "
        "The correct answer is the situation that best follows the stated rule."
    ),
}

_SYSTEM_PROMPT = """You are an expert LSAT question writer with deep knowledge of formal logic
and argumentation. You write Logical Reasoning questions that test a specific reasoning skill.

Output ONLY valid JSON matching the schema below. No markdown fences, no commentary, no extra fields.

Schema:
{
  "question_type": "<string>",
  "stimulus": "<string>",
  "stem": "<string>",
  "choices": [
    {"label": "A", "text": "<string>"},
    {"label": "B", "text": "<string>"},
    {"label": "C", "text": "<string>"},
    {"label": "D", "text": "<string>"},
    {"label": "E", "text": "<string>"}
  ],
  "correct_answer": "<A|B|C|D|E>",
  "explanation": "<one sentence explaining why the correct answer is right and each wrong answer is wrong>",
  "source": "generated"
}"""


@traceable(name="generate", metadata={"module": "generator"})
def generate(question_type: QuestionType, k: int = 3) -> Question:
    """Generate one LSAT question of the given type using RAG-grounded prompting.

    Retrieves k real LSAT questions of the same type as few-shot examples, then
    prompts claude-sonnet-4-6 to produce a structurally similar but novel question.
    The generation prompt pairs each example with type-specific instructions so the
    model understands what reasoning structure to replicate, not just surface phrasing.
    """
    examples = retrieve(
        query=f"LSAT {question_type.value.replace('_', ' ')} question",
        question_type=question_type,
        k=k,
    )

    examples_text = "\n\n".join(
        f"Example {i + 1}:\n{json.dumps(ex.model_dump(), indent=2)}"
        for i, ex in enumerate(examples)
    )

    type_instruction = _TYPE_INSTRUCTIONS.get(question_type, "")
    q_type_label = question_type.value.replace("_", " ").upper()

    user_prompt = f"""Question type to generate: {q_type_label}

Type-specific requirements:
{type_instruction}

Here are {len(examples)} real LSAT {q_type_label} question(s) for structural reference:

{examples_text if examples else "(no examples available — generate from type requirements alone)"}

Now write ONE new {q_type_label} question. Requirements:
- The stimulus must present a clear, self-contained argument or set of facts
- The stem must ask exactly what {q_type_label} requires (see type requirements above)
- There must be exactly ONE defensible correct answer
- The four wrong answers must be unambiguously incorrect (not merely less good)
- Do not copy or closely paraphrase any example above
- Use a different topic/domain than the examples
- Set "question_type" to exactly: "{question_type.value}" """

    messages = [{"role": "user", "content": user_prompt}]
    last_err: Exception | None = None

    for attempt in range(3):
        response = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        raw = response.content[0].text.strip()
        # Extract the JSON object in case Claude wraps it in prose or code fences
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start:end + 1]
        try:
            data = json.loads(raw)
            # Always enforce the correct snake_case enum value
            data["question_type"] = question_type.value
            data["source"] = QuestionSource.GENERATED.value
            return Question.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            last_err = e
            # Feed the bad output back so the model can self-correct
            messages = messages + [
                {"role": "assistant", "content": response.content[0].text},
                {"role": "user", "content": "That output was not valid JSON. Return only the JSON object with no trailing commas, comments, or prose."},
            ]

    raise ValueError(f"generate failed after 3 attempts: {last_err}")
