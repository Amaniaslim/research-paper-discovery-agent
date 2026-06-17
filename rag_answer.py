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
            "answer": "The indexed documents do not contain enough information to answer this question.",
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
        "Answer only based on the provided sources. If the answer is not in the sources, "
        "say that the documents do not contain enough information. Include source references "
        "in the answer in this format: [PDF name, page X].\n\n"
        f"Question: {question}\n\n"
        f"Sources:\n{sources}"
    )
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a careful PDF-RAG assistant. Use only the provided sources.",
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
        "SAIA is not available, so this fallback lists the most relevant retrieved PDF chunks.",
        "",
        f"Question: {question}",
        "",
    ]
    for index, chunk in enumerate(chunks, start=1):
        text = chunk["text"]
        preview = text[:700].rsplit(" ", 1)[0] + ("..." if len(text) > 700 else "")
        lines.extend(
            [
                f"{index}. [{chunk['pdf_name']}, page {chunk['page_number']}]",
                preview,
                "",
            ]
        )
    return "\n".join(lines).strip()


def _saia_enabled() -> bool:
    key = os.getenv("SAIA_API_KEY", "").strip()
    if not key or key.startswith("REPLACE_WITH"):
        return False
    return os.getenv("ENABLE_LLM_SUMMARIES", "true").strip().lower() in {"1", "true", "yes", "on"}
