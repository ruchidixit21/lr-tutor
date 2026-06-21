"""Embed corpus questions and load into Chroma vector store.

Reads data/corpus.jsonl, embeds stimulus + newline + stem for each Question
using Chroma's default embedding (all-MiniLM-L6-v2 via onnxruntime), then
upserts into the 'questions' collection. Safe to re-run — upsert is idempotent.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from src.db import get_collection
from src.models import Question

load_dotenv()


def load(corpus_file: str) -> None:
    path = Path(corpus_file)
    if not path.exists():
        print(f"Error: {corpus_file} not found", file=sys.stderr)
        sys.exit(1)

    lines = path.read_text().splitlines()
    questions: list[Question] = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            q = Question.model_validate(json.loads(line))
        except Exception as e:
            print(f"  [warn] line {i + 1}: parse error — {e}", file=sys.stderr)
            continue

        if not q.correct_answer:
            print(f"  [skip] {q.id[:8]}… — missing correct_answer", file=sys.stderr)
            continue

        questions.append(q)

    if not questions:
        print("No valid questions found. Nothing loaded.")
        return

    collection = get_collection()

    ids = [q.id for q in questions]
    documents = [f"{q.stimulus}\n{q.stem}" for q in questions]
    metadatas = [
        {
            "question_type": q.question_type.value,
            "source": q.source.value,
            "question_json": q.model_dump_json(),
        }
        for q in questions
    ]

    # upsert in batches of 100 to stay well within Chroma limits
    batch_size = 100
    for start in range(0, len(questions), batch_size):
        collection.upsert(
            ids=ids[start : start + batch_size],
            documents=documents[start : start + batch_size],
            metadatas=metadatas[start : start + batch_size],
        )

    total = collection.count()
    print(f"Loaded {len(questions)} questions. Collection now has {total} documents.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", default="data/corpus.jsonl", help="JSONL corpus file"
    )
    args = parser.parse_args()
    load(args.corpus)
