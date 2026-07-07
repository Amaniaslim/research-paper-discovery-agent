from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from review_core import LiteratureReview


SPRINT_DIR = Path(__file__).resolve().parent
DEFAULT_MEMORY_PATH = SPRINT_DIR / "demo_output" / "memory.json"
DEFAULT_CHROMA_PATH = SPRINT_DIR / "demo_output" / "chroma_memory"
DEFAULT_COLLECTION_NAME = "research_runs"


@dataclass
class MemoryDocument:
    page_content: str
    metadata: dict[str, str | int]


def remember_review(
    review: LiteratureReview,
    persist_path: Path = DEFAULT_MEMORY_PATH,
) -> str:
    """Store one completed review in ChromaDB, with JSON as a robust fallback."""
    memory_id = uuid4().hex
    saved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    top_papers = "\n".join(
        f"- {paper.title} (score: {paper.relevance_score})" for paper in review.papers
    )
    document = {
        "page_content": f"Research question: {review.query}\nTop papers:\n{top_papers}",
        "metadata": {
            "memory_id": memory_id,
            "query": review.query,
            "paper_count": len(review.papers),
            "saved_at": saved_at,
        },
    }

    collection = _get_chroma_collection()
    if collection is not None:
        collection.upsert(
            ids=[memory_id],
            documents=[document["page_content"]],
            metadatas=[document["metadata"]],
            embeddings=[_local_embedding(document["page_content"])],
        )
        return memory_id

    entries = _load_entries(persist_path)
    entries.append(document)
    persist_path.parent.mkdir(parents=True, exist_ok=True)
    persist_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return memory_id


def recall_reviews(
    query: str,
    limit: int = 3,
    persist_path: Path = DEFAULT_MEMORY_PATH,
) -> list[MemoryDocument]:
    """Retrieve earlier review sessions with simple keyword overlap."""
    clean_query = query.strip().lower()
    if not clean_query:
        return []

    collection = _get_chroma_collection()
    if collection is not None:
        result = collection.get(include=["documents", "metadatas"])
        entries = [
            {"page_content": document, "metadata": metadata}
            for document, metadata in zip(result.get("documents", []), result.get("metadatas", []))
        ]
        return _rank_entries(clean_query, entries, limit)

    if not persist_path.exists():
        return []

    return _rank_entries(clean_query, _load_entries(persist_path), limit)


def list_reviews(
    limit: int = 15,
    persist_path: Path = DEFAULT_MEMORY_PATH,
) -> list[MemoryDocument]:
    """Return the most recent stored research runs (newest first), like a history."""
    collection = _get_chroma_collection()
    if collection is not None:
        result = collection.get(include=["documents", "metadatas"])
        entries = [
            {"page_content": document, "metadata": metadata}
            for document, metadata in zip(result.get("documents", []), result.get("metadatas", []))
        ]
    else:
        entries = _load_entries(persist_path) if persist_path.exists() else []

    documents = [
        MemoryDocument(page_content=entry["page_content"], metadata=entry["metadata"])
        for entry in entries
    ]
    documents.sort(key=lambda doc: str(doc.metadata.get("saved_at", "")), reverse=True)
    return documents[:limit]


def memory_backend() -> str:
    """Return the active memory backend for the Streamlit demo."""
    if _get_chroma_collection() is not None:
        return f"ChromaDB ({DEFAULT_CHROMA_PATH})"
    return f"JSON fallback ({DEFAULT_MEMORY_PATH})"


def _rank_entries(clean_query: str, entries: list[dict], limit: int) -> list[MemoryDocument]:
    query_terms = set(clean_query.split())
    scored_entries = []
    for entry in entries:
        haystack = f"{entry['metadata'].get('query', '')} {entry['page_content']}".lower()
        score = sum(1 for term in query_terms if term in haystack)
        scored_entries.append((score, entry))

    scored_entries.sort(key=lambda item: item[0], reverse=True)
    return [
        MemoryDocument(page_content=entry["page_content"], metadata=entry["metadata"])
        for score, entry in scored_entries[:limit]
        if score > 0
    ]


def _get_chroma_collection():
    try:
        import chromadb
    except ImportError:
        return None

    try:
        DEFAULT_CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(DEFAULT_CHROMA_PATH))
        return client.get_or_create_collection(DEFAULT_COLLECTION_NAME)
    except Exception:
        return None


def _local_embedding(text: str, dimensions: int = 32) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append(round((byte / 127.5) - 1.0, 6))
    return values


def _load_entries(persist_path: Path) -> list[dict]:
    if not persist_path.exists():
        return []
    return json.loads(persist_path.read_text(encoding="utf-8"))
