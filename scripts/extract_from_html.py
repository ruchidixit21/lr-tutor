"""Parse structured HTML sources into Question objects."""
import argparse

# TODO: Phase 1


def main(url: str, output_file: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL to scrape")
    parser.add_argument("--output", default="data/corpus.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    main(args.url, args.output)
