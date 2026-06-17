from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


PROJECT_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(PROJECT_DIR / ".env")


def generate_answer(question: str, chunks: list[dict]) -> dict:
    """Generate a source-grounded answer from retrieved PDF chunks."""
    if not chunks:
        return {
            "answer": (
                "Auf Basis der gefundenen PDF-Quellen kann diese Frage nicht beantwortet werden. "
                "Es wurden keine passenden Textstellen im Index gefunden."
            ),
            "mode": "no_sources",
        }

    if _saia_enabled():
        try:
            return {"answer": _call_saia(question, chunks), "mode": "saia"}
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            pass

    return {"answer": _fallback_answer(question, chunks), "mode": "fallback"}


def _call_saia(question: str, chunks: list[dict]) -> str:
    api_key = os.getenv("SAIA_API_KEY", "").strip()
    base_url = os.getenv("SAIA_BASE_URL", "https://chat-ai.academiccloud.de/v1").strip().rstrip("/")
    model = os.getenv("SAIA_MODEL", "mistral-large-3-675b-instruct-2512").strip()
    sources = "\n\n".join(
        (
            f"Source {index}: [{chunk['pdf_name']}, page {chunk['page_number']}, chunk {chunk['chunk_id']}]\n"
            f"{chunk['text']}"
        )
        for index, chunk in enumerate(chunks, start=1)
    )
    prompt = (
        "Answer only based on the provided sources. Do not claim completeness, because only "
        "the top retrieved chunks are available. Start with: 'Auf Basis der gefundenen "
        "PDF-Quellen werden folgende Punkte genannt:' If the sources do not support a point, "
        "do not infer it. Connect every substantive statement to a source reference in this "
        "format: [PDF name, page X]. Do not write that the documents contain no further "
        "specific risks. If the question is about RAG, retrieval, vector databases, database "
        "execution, or embeddings, mention source-supported RAG controls first, especially "
        "access controls for vector databases, post-retrieval filtering, content verification "
        "before embedding, and rate-limiting. Mention general security measures only as "
        "additional points when they are supported by the sources.\n\n"
        f"Question: {question}\n\n"
        f"Sources:\n{sources}"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a careful PDF-RAG assistant. Use only the provided sources, "
                    "write cautiously, and avoid completeness claims."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ResearchPaperDiscoveryAgent/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    return response_payload["choices"][0]["message"]["content"].strip()


def _fallback_answer(question: str, chunks: list[dict]) -> str:
    lines = [
        "Auf Basis der gefundenen PDF-Quellen werden folgende Punkte genannt:",
        "",
        f"Frage: {question}",
        "",
    ]
    ordered_chunks = _prioritize_answer_chunks(question, chunks)
    if _is_rag_question(question):
        lines.extend(_rag_control_lines(ordered_chunks))
    for index, chunk in enumerate(ordered_chunks, start=1):
        text = chunk["text"]
        preview = _short_preview(text, limit=520)
        lines.extend(
            [
                f"{index}. {preview} [{chunk['pdf_name']}, page {chunk['page_number']}]",
                "",
            ]
        )
    lines.append(
        "Hinweis: Die Antwort basiert auf den gefundenen Top-Quellen und ist keine vollständige Analyse des gesamten Dokuments."
    )
    return "\n".join(lines).strip()


def _short_preview(text: str, limit: int) -> str:
    clean_text = " ".join(text.split())
    if len(clean_text) <= limit:
        return clean_text
    return clean_text[:limit].rsplit(" ", 1)[0] + "..."


def _prioritize_answer_chunks(question: str, chunks: list[dict]) -> list[dict]:
    if not _is_rag_question(question):
        return chunks
    return sorted(chunks, key=lambda chunk: _rag_control_score(chunk.get("text", "")), reverse=True)


def _rag_control_lines(chunks: list[dict]) -> list[str]:
    lines = []
    matched_controls = []
    for label, phrases in _RAG_CONTROL_PHRASES:
        chunk = _first_chunk_matching(chunks, phrases)
        if chunk is not None:
            matched_controls.append(
                f"- {label} [{chunk['pdf_name']}, page {chunk['page_number']}]"
            )
    if matched_controls:
        lines.extend(
            [
                "Spezifische RAG-/Retrieval-Kontrollen aus den gefundenen Quellen:",
                *matched_controls,
                "",
                "Ergänzende Auszüge aus den Top-Quellen:",
                "",
            ]
        )
    return lines


def _first_chunk_matching(chunks: list[dict], phrases: tuple[str, ...]) -> dict | None:
    for chunk in chunks:
        lower_text = chunk.get("text", "").lower()
        if any(phrase in lower_text for phrase in phrases):
            return chunk
    return None


def _rag_control_score(text: str) -> int:
    lower_text = text.lower()
    return sum(
        1
        for _label, phrases in _RAG_CONTROL_PHRASES
        for phrase in phrases
        if phrase in lower_text
    )


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


_RAG_CONTROL_PHRASES = (
    ("Access Controls für Vector Databases", ("access control", "access controls", "vector database", "vector databases")),
    ("Post-Retrieval Filtering", ("post-retrieval filtering", "retrieval filtering", "filter retrieved")),
    ("Content Verification vor Embedding", ("content verification", "before embedding", "verify content", "verified before embedding")),
    ("Rate-Limiting", ("rate-limiting", "rate limiting", "rate limit")),
)


def _saia_enabled() -> bool:
    key = os.getenv("SAIA_API_KEY", "").strip()
    if not key or key.startswith("REPLACE_WITH"):
        return False
    return os.getenv("ENABLE_LLM_SUMMARIES", "true").strip().lower() in {"1", "true", "yes", "on"}
