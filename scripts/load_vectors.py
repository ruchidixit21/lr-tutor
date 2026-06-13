"""Embed corpus questions and load into Chroma vector store."""
import argparse

# TODO: Phase 1


def main(corpus_file: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/corpus.jsonl", help="JSONL corpus file")
    args = parser.parse_args()
    main(args.corpus)
