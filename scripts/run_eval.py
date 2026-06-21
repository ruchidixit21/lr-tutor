"""Batch eval runner: score a set of questions with the rubric scorer and append results.

Reads a JSONL file of Questions, scores each with src/scorer.py, and appends
RubricScore objects to the output JSONL. Prints a summary table on completion.

Usage:
  # Score generated questions
  uv run scripts/run_eval.py eval/generated_samples.jsonl

  # Score real LSAT questions (ceiling calibration — should average ≥4.0)
  uv run scripts/run_eval.py data/corpus.jsonl --output eval/ground_truth_scores.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.models import Question, RubricScore
from src.scorer import score

load_dotenv()


def run(input_file: str, output_file: str, limit: int | None) -> None:
    in_path = Path(input_file)
    if not in_path.exists():
        print(f"Error: {input_file} not found", file=sys.stderr)
        sys.exit(1)

    lines = [l.strip() for l in in_path.read_text().splitlines() if l.strip()]
    if limit:
        lines = lines[:limit]

    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scores: list[RubricScore] = []
    for i, line in enumerate(lines):
        try:
            q = Question.model_validate(json.loads(line))
        except Exception as e:
            print(f"  [skip] line {i + 1}: {e}", file=sys.stderr)
            continue

        print(f"  Scoring {i + 1}/{len(lines)}: {q.id[:8]}… ", end="", flush=True)
        try:
            rubric = score(q)
            scores.append(rubric)
            print(f"avg={rubric.average:.1f}  "
                  f"[lv={rubric.logical_validity} au={rubric.answer_uniqueness} "
                  f"dq={rubric.distractor_quality} ta={rubric.type_accuracy} "
                  f"si={rubric.stimulus_independence}]")
        except Exception as e:
            print(f"FAILED — {e}", file=sys.stderr)

    if not scores:
        print("No questions scored.")
        return

    with open(out_path, "a") as f:
        for s in scores:
            f.write(s.model_dump_json() + "\n")

    avg = sum(s.average for s in scores) / len(scores)
    dims = ["logical_validity", "answer_uniqueness", "distractor_quality",
            "type_accuracy", "stimulus_independence"]
    print(f"\n{'─' * 55}")
    print(f"  Scored {len(scores)} questions  →  overall average: {avg:.2f}")
    for dim in dims:
        val = sum(getattr(s, dim) for s in scores) / len(scores)
        print(f"    {dim:<25} {val:.2f}")
    print(f"{'─' * 55}")
    print(f"Results appended to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_file", help="JSONL file of Questions to score")
    parser.add_argument("--output", default="eval/generated_samples.jsonl",
                        help="Output JSONL file for RubricScores (appended)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Stop after N questions (useful for spot checks)")
    args = parser.parse_args()
    run(args.input_file, args.output, args.limit)
