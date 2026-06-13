"""Batch eval runner: score a set of questions with the rubric scorer."""
import argparse

# TODO: Phase 2


def main(input_file: str, output_file: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", help="JSONL file of Questions to score")
    parser.add_argument("--output", default="eval/generated_samples.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    main(args.input_file, args.output)
