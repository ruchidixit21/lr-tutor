"""Extract Question objects from scanned JPEG/PNG pages via Claude vision API.

Prompt strategy: send each image to claude-sonnet-4-6 with a system prompt that
defines the Question JSON schema and all 15 question type patterns. Ask for a
strict JSON array with no commentary. Parse and validate with Pydantic, then
append valid questions to the output JSONL file.
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from dotenv import load_dotenv

from src.models import AnswerChoice, Question, QuestionSource, QuestionType

load_dotenv()

SYSTEM_PROMPT = """You are an expert at extracting LSAT Logical Reasoning questions from scanned test pages.

Extract every LSAT Logical Reasoning question visible on the page and output a JSON array.
Each element must exactly match this schema — no extra fields, no commentary, no markdown:

{
  "question_type": "<see types below>",
  "stimulus": "<the argument or passage text, verbatim>",
  "stem": "<the question being asked, verbatim>",
  "choices": [
    {"label": "A", "text": "<choice text verbatim>"},
    {"label": "B", "text": "<choice text verbatim>"},
    {"label": "C", "text": "<choice text verbatim>"},
    {"label": "D", "text": "<choice text verbatim>"},
    {"label": "E", "text": "<choice text verbatim>"}
  ],
  "correct_answer": "<A/B/C/D/E if shown on page, otherwise empty string>",
  "source": "real_lsat",
  "source_detail": "<e.g. PrepTest 71 Section 2 Q14, or page number if visible>"
}

Question type values and their stem markers:
- "assumption_necessary"  → "assumes", "the argument requires the assumption"
- "assumption_sufficient" → "if assumed, allows the conclusion to be properly drawn"
- "strengthen"           → "most strengthens", "provides the most support for"
- "weaken"              → "most weakens", "most seriously undermines"
- "flaw"                → "flaw in the reasoning", "the reasoning is flawed because"
- "inference"           → "can be properly inferred", "most strongly supported by"
- "must_be_true"        → "must be true", "must also be true"
- "cannot_be_true"      → "cannot be true", "is impossible"
- "paradox"             → "helps to explain", "resolve the apparent discrepancy"
- "parallel_reasoning"  → "most similar in its reasoning", "most parallel in structure"
- "parallel_flaw"       → "most similar flaw", "contains a flaw most similar to"
- "point_of_disagreement" → "disagree about", "point of disagreement"
- "evaluate"            → "most useful to know", "most helpful in evaluating"
- "principle_identify"  → "best illustrates which principle", "principle most illustrated"
- "principle_apply"     → "most in accord with the principle", "most consistent with"

Rules:
- Include all 5 answer choices always. If a choice is cut off, include what is visible.
- If the correct answer is not shown on this page, use empty string "".
- If a field cannot be determined, use empty string "".
- If there are no LR questions on this page, output: []
- Output ONLY the JSON array. No markdown fences. No explanation."""


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    raise ValueError(f"Unsupported image type: {suffix}")


def extract_from_image(image_path: Path, client: anthropic.Anthropic) -> list[Question]:
    """Call Claude vision API on one image, return validated Question objects."""
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type(image_path),
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all LSAT Logical Reasoning questions from this page.",
                    },
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [warn] {image_path.name}: Claude returned invalid JSON — {e}", file=sys.stderr)
        return []

    if not isinstance(data, list):
        print(f"  [warn] {image_path.name}: expected JSON array, got {type(data).__name__}", file=sys.stderr)
        return []

    questions: list[Question] = []
    for i, item in enumerate(data):
        try:
            q = Question.model_validate(item)
            questions.append(q)
        except Exception as e:
            print(f"  [warn] {image_path.name} item {i}: validation failed — {e}", file=sys.stderr)

    return questions


def main(image_dir: str, output_file: str, source_detail_prefix: str) -> None:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    image_dir_path = Path(image_dir)
    if not image_dir_path.is_dir():
        print(f"Error: {image_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    images = sorted(
        p for p in image_dir_path.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp")
    )

    if not images:
        print(f"No image files found in {image_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with open(output_path, "a") as out:
        for img in images:
            print(f"Processing {img.name}...")
            questions = extract_from_image(img, client)
            for q in questions:
                if not q.source_detail and source_detail_prefix:
                    q.source_detail = f"{source_detail_prefix} — {img.name}"
                out.write(q.model_dump_json() + "\n")
            print(f"  → {len(questions)} question(s) extracted")
            total += len(questions)

    print(f"\nDone. {total} questions written to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", help="Directory of JPEG/PNG scan files")
    parser.add_argument(
        "--output", default="data/corpus.jsonl", help="Output JSONL file (appended)"
    )
    parser.add_argument(
        "--source-detail-prefix",
        default="",
        help='Prefix for source_detail field, e.g. "LSAC Free Sample Test"',
    )
    args = parser.parse_args()
    main(args.image_dir, args.output, args.source_detail_prefix)
