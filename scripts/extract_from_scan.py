"""Extract Question objects from scanned JPEG/PNG pages via Claude vision API."""
import argparse

# TODO: Phase 1


def main(image_dir: str, output_file: str) -> None:
    raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_dir", help="Directory of JPEG/PNG scan files")
    parser.add_argument("--output", default="data/corpus.jsonl", help="Output JSONL file")
    args = parser.parse_args()
    main(args.image_dir, args.output)
