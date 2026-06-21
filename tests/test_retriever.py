"""Tests for src/retriever.py using an in-memory Chroma collection."""
import json
from pathlib import Path
from unittest.mock import patch

import chromadb
import pytest

from src.models import Question, QuestionType
from src.retriever import retrieve

FIXTURES = Path(__file__).parent / "fixtures" / "mini_corpus.jsonl"


@pytest.fixture(scope="module")
def populated_collection() -> chromadb.Collection:
    """Load fixture questions into an ephemeral (in-memory) Chroma collection."""
    client = chromadb.EphemeralClient()
    collection = client.get_or_create_collection(
        name="test_questions",
        metadata={"hnsw:space": "cosine"},
    )

    questions: list[Question] = []
    for line in FIXTURES.read_text().splitlines():
        line = line.strip()
        if line:
            questions.append(Question.model_validate(json.loads(line)))

    collection.upsert(
        ids=[q.id for q in questions],
        documents=[f"{q.stimulus}\n{q.stem}" for q in questions],
        metadatas=[
            {
                "question_type": q.question_type.value,
                "source": q.source.value,
                "question_json": q.model_dump_json(),
            }
            for q in questions
        ],
    )
    return collection


def test_fixture_corpus_has_ten_questions(populated_collection):
    assert populated_collection.count() == 10


def test_retrieve_returns_questions(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("causal argument about diet and weight", k=3)
    assert len(results) > 0
    assert all(isinstance(q, Question) for q in results)


def test_retrieve_respects_k(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("argument about a study", k=2)
    assert len(results) <= 2


def test_retrieve_type_filter_weaken(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("undermine an argument", question_type=QuestionType.WEAKEN, k=5)
    assert all(q.question_type == QuestionType.WEAKEN for q in results)


def test_retrieve_type_filter_returns_only_matching_type(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("reasoning structure", question_type=QuestionType.FLAW, k=5)
    assert all(q.question_type == QuestionType.FLAW for q in results)


def test_retrieve_no_filter_returns_mixed_types(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("argument", k=10)
    types = {q.question_type for q in results}
    assert len(types) > 1, "Unfiltered retrieval should return multiple question types"


def test_retrieved_questions_have_correct_answer(populated_collection):
    with patch("src.retriever.get_collection", return_value=populated_collection):
        results = retrieve("study shows correlation", k=5)
    assert all(q.correct_answer in ("A", "B", "C", "D", "E") for q in results)
