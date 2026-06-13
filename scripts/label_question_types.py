"""Classify question_type from stem text for Questions where it is missing."""
import argparse

# TODO: Phase 1


def main(input_file: str, output_file: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", help="JSONL file with unlabeled Questions")
    parser.add_argument("--output", default="data/corpus.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    main(args.input_file, args.output)
