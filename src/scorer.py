import json
import os

import anthropic

from src.models import Question, RubricScore

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_SYSTEM_PROMPT = """You are an expert LSAT question evaluator. Score the given question on five
dimensions, each from 1 to 5. Be strict — a score of 5 should be rare and means the question
is indistinguishable from an official LSAT question. Real LSAT questions should average ≥4.0.

Dimensions:
1. logical_validity (1–5): Does the argument gap actually exist? Is the reasoning structure
   sound and non-trivial? 1 = the argument is incoherent or the gap doesn't exist; 5 = the
   argument is tight, the gap is real and non-obvious.

2. answer_uniqueness (1–5): Is there exactly one defensible correct answer? Could a well-
   prepared LSAT student reasonably defend any other choice? 1 = multiple answers are
   defensible; 5 = only one answer is correct and it is clearly correct.

3. distractor_quality (1–5): Are the wrong answers unambiguously incorrect? Do they tempt
   without being defensible? 1 = distractors are obviously wrong or irrelevant; 5 = each
   distractor is tempting but clearly wrong on close analysis.

4. type_accuracy (1–5): Does the question actually test what its question_type claims?
   1 = the stem/answer pattern is mismatched to the type; 5 = perfectly tests the stated type.

5. stimulus_independence (1–5): Can the question be answered using only the stimulus and
   general reasoning, without outside knowledge? 1 = requires specialized knowledge;
   5 = fully self-contained.

Output ONLY valid JSON — no markdown fences, no commentary:
{
  "logical_validity": <1-5>,
  "answer_uniqueness": <1-5>,
  "distractor_quality": <1-5>,
  "type_accuracy": <1-5>,
  "stimulus_independence": <1-5>,
  "notes": "<one sentence: main strength and main weakness, or null>"
}"""


def score(question: Question) -> RubricScore:
    """Score a Question on the five rubric dimensions using claude-sonnet-4-6.

    The system prompt defines each 1–5 dimension in detail and is calibrated so that
    real LSAT questions should average ≥4.0. Returns a RubricScore with an `.average`
    property. Used both for ceiling calibration (real questions) and to evaluate
    generated questions against the baseline.
    """
    question_text = json.dumps(question.model_dump(), indent=2)

    response = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Score this LSAT question:\n\n{question_text}",
            }
        ],
    )

    raw = response.content[0].text.strip()
    data = json.loads(raw)
    data["question_id"] = question.id
    return RubricScore.model_validate(data)
