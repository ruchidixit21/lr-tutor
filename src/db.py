import os
import chromadb
import chromadb.api
from chromadb.config import Settings

_client: chromadb.api.ClientAPI | None = None


def get_client() -> chromadb.api.ClientAPI:
    global _client
    if _client is None:
        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str = "questions") -> chromadb.Collection:
    return get_client().get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )
