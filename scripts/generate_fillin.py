"""Generate fill-in questions for under-represented question types.

Reads data/corpus.jsonl, finds types below --min-count (default 5), generates
questions for each gap using src/generator.py, scores each with src/scorer.py,
and appends questions that meet --min-score (default 3.5) to the corpus.

Questions that fail the score threshold are logged but not saved — review them
manually if you want to override.

Usage:
  uv run scripts/generate_fillin.py
  uv run scripts/generate_fillin.py --min-count 5 --min-score 3.5 --attempts 3
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.generator import generate
from src.models import QuestionType
from src.scorer import score

load_dotenv()

ALL_TYPES = list(QuestionType)


def run(corpus_file: str, min_count: int, min_score: float, attempts: int) -> None:
    path = Path(corpus_file)
    lines = [l.strip() for l in path.read_text().splitlines() if l.strip()]

    counts: Counter = Counter()
    for line in lines:
        data = json.loads(line)
        counts[data["question_type"]] += 1

    gaps = {qt: max(0, min_count - counts.get(qt.value, 0)) for qt in ALL_TYPES}
    gaps = {qt: n for qt, n in gaps.items() if n > 0}

    if not gaps:
        print(f"All types already have ≥{min_count} questions. Nothing to generate.")
        return

    print(f"Gaps to fill (target ≥{min_count} per type):")
    for qt, n in gaps.items():
        print(f"  {qt.value:<30} have {counts.get(qt.value, 0)}, need {n} more")
    print()

    saved = 0
    rejected = 0

    with open(path, "a") as out:
        for qt, needed in gaps.items():
            generated_for_type = 0
            attempt = 0

            while generated_for_type < needed:
                attempt += 1
                if attempt > needed * attempts:
                    print(f"  [{qt.value}] giving up after {attempt - 1} attempts "
                          f"({generated_for_type}/{needed} saved)")
                    break

                print(f"  [{qt.value}] attempt {attempt} … ", end="", flush=True)
                try:
                    q = generate(qt)
                except Exception as e:
                    print(f"generation failed — {e}")
                    continue

                try:
                    rubric = score(q)
                except Exception as e:
                    print(f"scoring failed — {e}")
                    continue

                avg = rubric.average
                if avg >= min_score:
                    out.write(q.model_dump_json() + "\n")
                    print(f"✓ saved  avg={avg:.1f}")
                    generated_for_type += 1
                    saved += 1
                else:
                    print(f"✗ rejected  avg={avg:.1f} < {min_score}")
                    rejected += 1

    print(f"\nDone. {saved} questions saved, {rejected} rejected (score < {min_score}).")
    print("Run `uv run scripts/load_vectors.py` to index new questions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", default="data/corpus.jsonl")
    parser.add_argument("--min-count", type=int, default=5,
                        help="Target minimum questions per type (default: 5)")
    parser.add_argument("--min-score", type=float, default=3.5,
                        help="Minimum rubric average to accept a generated question (default: 3.5)")
    parser.add_argument("--attempts", type=int, default=3,
                        help="Max attempts per needed question before giving up (default: 3)")
    args = parser.parse_args()
    run(args.corpus, args.min_count, args.min_score, args.attempts)
