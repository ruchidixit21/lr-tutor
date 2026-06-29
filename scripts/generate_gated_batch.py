"""Generate a batch of questions using the gated generator and save to JSONL.

Generates `--per-type` questions for each QuestionType (default 2), saving
the Question objects to the output file. Also saves a sidecar file with the
rubric scores from the gating process (so you don't need to re-score them).

Usage:
    uv run scripts/generate_gated_batch.py
    uv run scripts/generate_gated_batch.py --per-type 3 --out eval/gated_batch.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.generator_gated import generate_gated
from src.models import QuestionType


def run(per_type: int, out: Path, scores_out: Path) -> None:
    types = list(QuestionType)
    total = per_type * len(types)
    print(f"Generating {per_type} question(s) × {len(types)} types = {total} total\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    scores_out.parent.mkdir(parents=True, exist_ok=True)

    saved = 0
    with out.open("a") as qf, scores_out.open("a") as sf:
        for qt in types:
            for i in range(per_type):
                label = f"{qt.value} [{i + 1}/{per_type}]"
                print(f"  {label:<45}", end="", flush=True)
                try:
                    q, s = generate_gated(qt)
                    qf.write(q.model_dump_json() + "\n")
                    sf.write(s.model_dump_json() + "\n")
                    saved += 1
                    print(f"avg={s.average:.2f}")
                except Exception as e:
                    print(f"FAILED — {e}", file=sys.stderr)

    print(f"\nSaved {saved}/{total} questions → {out}")
    print(f"Rubric scores → {scores_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--per-type", type=int, default=2,
                        help="Questions to generate per QuestionType (default: 2)")
    parser.add_argument("--out", type=Path, default=Path("eval/gated_batch.jsonl"),
                        help="Output JSONL for Question objects (default: eval/gated_batch.jsonl)")
    parser.add_argument("--scores-out", type=Path, default=Path("eval/generated_samples.jsonl"),
                        help="Output JSONL for RubricScores (default: eval/generated_samples.jsonl)")
    args = parser.parse_args()
    run(args.per_type, args.out, args.scores_out)
