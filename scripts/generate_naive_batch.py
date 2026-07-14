"""Generate a batch of LSAT questions using a naive prompt (no RAG, no schema).

This is the baseline condition for the comparison against RAG-grounded generation.
The prompt is intentionally minimal: just "write an LSAT logical reasoning question"
with no retrieved examples, no type specification, and no structured output requirements.

Questions that fail Pydantic validation are counted as failures and skipped.
The failure rate itself is part of the comparison story.

Usage:
    uv run scripts/generate_naive_batch.py
    uv run scripts/generate_naive_batch.py --n 30 --out eval/naive_batch.jsonl
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import anthropic

from src.models import AnswerChoice, Question, QuestionSource, QuestionType

_NAIVE_PROMPT = """Write one LSAT Logical Reasoning question. Include a stimulus (a short argument or set of facts), a question stem, five answer choices labeled A through E, and indicate the correct answer."""

_PARSE_SYSTEM = """You are a JSON extractor. The user will give you an LSAT question in any format.
Extract it into this exact JSON schema with no extra fields and no markdown fences:
{
  "question_type": "<one of: assumption_necessary, assumption_sufficient, strengthen, weaken, flaw, inference, must_be_true, cannot_be_true, paradox, parallel_reasoning, parallel_flaw, point_of_disagreement, evaluate, principle_identify, principle_apply>",
  "stimulus": "<the argument or passage>",
  "stem": "<the question being asked>",
  "choices": [
    {"label": "A", "text": "<text>"},
    {"label": "B", "text": "<text>"},
    {"label": "C", "text": "<text>"},
    {"label": "D", "text": "<text>"},
    {"label": "E", "text": "<text>"}
  ],
  "correct_answer": "<A|B|C|D|E>",
  "source": "generated"
}
Infer question_type from the stem wording. Output only the JSON object."""


def generate_naive(client: anthropic.Anthropic) -> str:
    """Call Claude with the minimal naive prompt, return raw text."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": _NAIVE_PROMPT}],
    )
    return response.content[0].text.strip()


def parse_to_question(client: anthropic.Anthropic, raw: str) -> Question | None:
    """Use a second Claude call to parse raw text into the Question schema."""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_PARSE_SYSTEM,
        messages=[{"role": "user", "content": raw}],
    )
    text = response.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start:end + 1])
        data["source"] = QuestionSource.GENERATED.value
        return Question.model_validate(data)
    except Exception:
        return None


def run(n: int, out: Path, scores_out: Path) -> None:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    out.parent.mkdir(parents=True, exist_ok=True)
    scores_out.parent.mkdir(parents=True, exist_ok=True)

    # Import scorer here so load_dotenv has already run
    from src.scorer import score

    saved = 0
    failed = 0

    with out.open("a") as qf, scores_out.open("a") as sf:
        for i in range(n):
            print(f"  [{i + 1}/{n}] generating...", end="", flush=True)
            try:
                raw = generate_naive(client)
                question = parse_to_question(client, raw)
                if question is None:
                    raise ValueError("parse returned None")
                rubric = score(question)
                qf.write(question.model_dump_json() + "\n")
                sf.write(rubric.model_dump_json() + "\n")
                saved += 1
                print(f" avg={rubric.average:.2f}  [{question.question_type.value}]")
            except Exception as e:
                failed += 1
                print(f" FAILED — {e}", file=sys.stderr)

    total = saved + failed
    print(f"\nSaved {saved}/{total}  |  failed {failed}/{total}")
    print(f"Questions → {out}")
    print(f"Scores    → {scores_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=30, help="Number of questions to generate")
    parser.add_argument("--out", type=Path, default=Path("eval/naive_batch.jsonl"))
    parser.add_argument("--scores-out", type=Path, default=Path("eval/naive_scores.jsonl"))
    args = parser.parse_args()
    run(args.n, args.out, args.scores_out)
