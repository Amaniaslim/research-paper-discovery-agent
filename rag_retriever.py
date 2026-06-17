from __future__ import annotations

import re

import rag_store


def search_relevant_chunks(question: str, top_k: int = 5) -> list[dict]:
    """Retrieve relevant PDF chunks with ChromaDB, then JSON/keyword fallback."""
    clean_question = question.strip()
    if not clean_question:
        return []

    chroma_results = rag_store.query_chunks(clean_question, top_k=top_k)
    if chroma_results:
        return [_format_result(result) for result in chroma_results[:top_k]]

    entries = rag_store.load_all_chunks()
    scored = []
    question_terms = _terms(clean_question)
    for entry in entries:
        document = entry.get("document", "")
        text_terms = _terms(document)
        score = len(question_terms & text_terms)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [_format_result(entry, score=score) for score, entry in scored[:top_k]]


def _format_result(entry: dict, score: float | int | None = None) -> dict:
    metadata = entry.get("metadata", {})
    return {
        "text": entry.get("document", ""),
        "pdf_name": metadata.get("pdf_name", "unknown.pdf"),
        "page_number": metadata.get("page_number", 0),
        "chunk_id": metadata.get("chunk_id", entry.get("id", "")),
        "score": score if score is not None else entry.get("distance"),
    }


def _terms(text: str) -> set[str]:
    return {term for term in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.lower()) if term not in _STOPWORDS}


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "are",
    "was",
    "were",
    "into",
    "their",
    "there",
    "have",
    "has",
    "paper",
}
