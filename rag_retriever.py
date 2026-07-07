from __future__ import annotations

import re

import rag_store


def search_relevant_chunks(
    question: str,
    top_k: int = 5,
    sections: list[str] | None = None,
    neighbor_radius: int = 0,
) -> list[dict]:
    """Retrieve relevant PDF chunks with ChromaDB, then JSON/keyword fallback.

    ``neighbor_radius`` optionally pulls in adjacent chunks on the same page for
    more context, e.g. radius 1 adds p60-c0/p60-c2 around a retrieved p60-c1.
    """
    clean_question = question.strip()
    if not clean_question:
        return []

    selected_sections = {section for section in (sections or []) if section and section != "Alle Sektionen"}
    search_limit = max(top_k * 8, top_k)
    chroma_results = rag_store.query_chunks(clean_question, top_k=search_limit)
    if chroma_results:
        formatted = [_format_result(result) for result in chroma_results]
        formatted = _filter_by_sections(formatted, selected_sections)
        ranked = _rank_formatted_results(clean_question, formatted)[:top_k]
        return _expand_with_neighbors(ranked, neighbor_radius)

    entries = rag_store.load_all_chunks()
    scored = []
    for entry in entries:
        metadata = entry.get("metadata", {})
        if selected_sections and metadata.get("section", "Unbekannt") not in selected_sections:
            continue
        score = _keyword_score(clean_question, entry.get("document", ""))
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    ranked = [_format_result(entry, score=score) for score, entry in scored[:top_k]]
    return _expand_with_neighbors(ranked, neighbor_radius)


_CHUNK_ID_PATTERN = re.compile(r"p(\d+)-c(\d+)")


def _expand_with_neighbors(results: list[dict], neighbor_radius: int) -> list[dict]:
    """Insert adjacent same-page chunks next to each retrieved result."""
    if neighbor_radius <= 0 or not results:
        return results

    lookup: dict[tuple[str, str], dict] = {}
    for entry in rag_store.load_all_chunks():
        metadata = entry.get("metadata", {})
        key = (str(metadata.get("pdf_name", "")), str(metadata.get("chunk_id", entry.get("id", ""))))
        lookup[key] = entry

    expanded: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for result in results:
        pdf_name = str(result.get("pdf_name", ""))
        chunk_id = str(result.get("chunk_id", ""))
        match = _CHUNK_ID_PATTERN.fullmatch(chunk_id)
        neighbors_before: list[dict] = []
        neighbors_after: list[dict] = []
        if match:
            page_no, chunk_no = int(match.group(1)), int(match.group(2))
            for delta in range(-neighbor_radius, neighbor_radius + 1):
                if delta == 0:
                    continue
                neighbor_id = f"p{page_no}-c{chunk_no + delta}"
                key = (pdf_name, neighbor_id)
                if key in seen or key not in lookup:
                    continue
                neighbor = _format_result(lookup[key])
                neighbor["retrieval_score"] = round(float(result.get("retrieval_score", 0)) * 0.5, 4)
                neighbor["is_context"] = True
                seen.add(key)
                (neighbors_before if delta < 0 else neighbors_after).append(neighbor)
        expanded.extend(neighbors_before)
        result_key = (pdf_name, chunk_id)
        if result_key not in seen:
            seen.add(result_key)
            expanded.append(result)
        expanded.extend(neighbors_after)
    return expanded


def _format_result(entry: dict, score: float | int | None = None) -> dict:
    metadata = entry.get("metadata", {})
    return {
        "text": entry.get("document", ""),
        "pdf_name": metadata.get("pdf_name", "unknown.pdf"),
        "page_number": metadata.get("page_number", 0),
        "chunk_id": metadata.get("chunk_id", entry.get("id", "")),
        "section": metadata.get("section", "Unbekannt"),
        "extraction_method": metadata.get("extraction_method", "pdf_text"),
        "score": score if score is not None else entry.get("distance"),
    }


def _filter_by_sections(results: list[dict], selected_sections: set[str]) -> list[dict]:
    if not selected_sections:
        return results
    return [result for result in results if result.get("section", "Unbekannt") in selected_sections]


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
