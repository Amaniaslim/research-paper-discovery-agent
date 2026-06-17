from __future__ import annotations

import re

import rag_store


def search_relevant_chunks(question: str, top_k: int = 5) -> list[dict]:
    """Retrieve relevant PDF chunks with ChromaDB, then JSON/keyword fallback."""
    clean_question = question.strip()
    if not clean_question:
        return []

    search_limit = max(top_k * 4, top_k)
    chroma_results = rag_store.query_chunks(clean_question, top_k=search_limit)
    if chroma_results:
        formatted = [_format_result(result) for result in chroma_results]
        return _rank_formatted_results(clean_question, formatted)[:top_k]

    entries = rag_store.load_all_chunks()
    scored = []
    for entry in entries:
        score = _keyword_score(clean_question, entry.get("document", ""))
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


def _rank_formatted_results(question: str, results: list[dict]) -> list[dict]:
    ranked = []
    for result in results:
        keyword_score = _keyword_score(question, result.get("text", ""))
        distance = result.get("score")
        distance_score = 0.0
        if isinstance(distance, (int, float)):
            distance_score = max(0.0, 1.0 - float(distance))
        result["retrieval_score"] = round(keyword_score + distance_score, 4)
        ranked.append(result)
    return sorted(ranked, key=lambda item: item.get("retrieval_score", 0), reverse=True)


def _keyword_score(question: str, text: str) -> float:
    question_terms = _terms(question)
    text_terms = _terms(text)
    score = float(len(question_terms & text_terms))
    if _is_rag_question(question):
        lower_text = text.lower()
        for phrase, weight in _RAG_PRIORITY_PHRASES.items():
            if phrase in lower_text:
                score += weight
        for term in _RAG_PRIORITY_TERMS:
            if term in text_terms:
                score += 2.0
    return score


def _is_rag_question(question: str) -> bool:
    lower_question = question.lower()
    return any(trigger in lower_question for trigger in _RAG_QUERY_TRIGGERS)


_RAG_QUERY_TRIGGERS = {
    "rag",
    "retrieval",
    "vector database",
    "vector databases",
    "database execution",
    "embedding",
    "embeddings",
}


_RAG_PRIORITY_TERMS = {
    "rag",
    "retrieval",
    "vector",
    "database",
    "databases",
    "embedding",
    "embeddings",
    "filtering",
    "verification",
    "rate-limiting",
    "ratelimiting",
}


_RAG_PRIORITY_PHRASES = {
    "vector database": 5.0,
    "vector databases": 5.0,
    "database execution": 5.0,
    "access control": 4.0,
    "access controls": 4.0,
    "post-retrieval filtering": 4.0,
    "content verification": 4.0,
    "before embedding": 3.0,
    "rate-limiting": 3.0,
    "rate limiting": 3.0,
    "retrieval augmented generation": 3.0,
}


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
