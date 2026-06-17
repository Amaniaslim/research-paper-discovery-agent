from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_CHROMA_PATH = PROJECT_DIR / "demo_output" / "pdf_chroma"
DEFAULT_CACHE_PATH = PROJECT_DIR / "demo_output" / "pdf_chunks_cache.json"
COLLECTION_NAME = "paper_chunks"


def store_chunks(
    chunks: list[dict],
    persist_path: Path = DEFAULT_CHROMA_PATH,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> dict:
    """Store PDF chunks in ChromaDB, with JSON fallback if ChromaDB is unavailable."""
    if not chunks:
        return {"backend": "none", "stored_chunks": 0, "message": "No chunks to store."}

    collection = _get_collection(persist_path)
    if collection is not None:
        ids = [stable_chunk_id(chunk) for chunk in chunks]
        collection.upsert(
            ids=ids,
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[_metadata(chunk) for chunk in chunks],
            embeddings=[local_embedding(chunk["text"]) for chunk in chunks],
        )
        return {"backend": "chromadb", "stored_chunks": len(chunks), "message": "Chunks stored in ChromaDB."}

    entries = _load_cache(cache_path)
    by_id = {entry["id"]: entry for entry in entries}
    for chunk in chunks:
        chunk_id = stable_chunk_id(chunk)
        by_id[chunk_id] = {
            "id": chunk_id,
            "document": chunk["text"],
            "metadata": _metadata(chunk),
        }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(list(by_id.values()), indent=2), encoding="utf-8")
    return {"backend": "json", "stored_chunks": len(chunks), "message": f"Chunks stored in {cache_path}."}


def load_all_chunks(
    persist_path: Path = DEFAULT_CHROMA_PATH,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> list[dict]:
    """Load all chunks from ChromaDB or JSON fallback."""
    collection = _get_collection(persist_path)
    if collection is not None:
        result = collection.get(include=["documents", "metadatas"])
        return [
            {"id": item_id, "document": document, "metadata": metadata}
            for item_id, document, metadata in zip(
                result.get("ids", []),
                result.get("documents", []),
                result.get("metadatas", []),
            )
        ]
    return _load_cache(cache_path)


def query_chunks(
    question: str,
    top_k: int = 5,
    persist_path: Path = DEFAULT_CHROMA_PATH,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> list[dict]:
    """Query chunks by vector similarity when ChromaDB is available."""
    collection = _get_collection(persist_path)
    if collection is None:
        return []

    result = collection.query(
        query_embeddings=[local_embedding(question)],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    ids = result.get("ids", [[]])[0]
    return [
        {
            "id": item_id,
            "document": document,
            "metadata": metadata,
            "distance": distance,
        }
        for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances)
    ]


def storage_backend(persist_path: Path = DEFAULT_CHROMA_PATH) -> str:
    return "ChromaDB" if _get_collection(persist_path) is not None else "JSON fallback"


def stable_chunk_id(chunk: dict) -> str:
    raw = f"{chunk['pdf_name']}|{chunk['page_number']}|{chunk['chunk_id']}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"pdfchunk-{digest}"


def local_embedding(text: str, dimensions: int = 64) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append(round((byte / 127.5) - 1.0, 6))
    return values


def _get_collection(persist_path: Path):
    try:
        import chromadb
    except ImportError:
        return None

    try:
        persist_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_path))
        return client.get_or_create_collection(COLLECTION_NAME)
    except Exception:
        return None


def _metadata(chunk: dict) -> dict:
    return {
        "pdf_name": chunk["pdf_name"],
        "page_number": int(chunk["page_number"]),
        "chunk_id": chunk["chunk_id"],
    }


def _load_cache(cache_path: Path) -> list[dict]:
    if not cache_path.exists():
        return []
    return json.loads(cache_path.read_text(encoding="utf-8"))
