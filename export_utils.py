"""CSV and Excel export helpers for retrieved PDF-RAG sources.

Each exported row describes one retrieved source chunk together with the shared
context (question, answer, embedding model, OCR mode, selected page range and a
timestamp), so a single file is self-contained for later review.
"""

from __future__ import annotations

import csv
import io

EXPORT_COLUMNS = [
    "question",
    "answer",
    "pdf_name",
    "page_number",
    "chunk_id",
    "section",
    "extraction_method",
    "score",
    "text_excerpt",
    "timestamp",
    "embedding_model",
    "ocr_mode",
    "page_range",
]


def _excerpt(text: str, limit: int = 650) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0] + "..."


def build_rows(
    question: str,
    answer: str,
    chunks: list[dict],
    timestamp: str,
    embedding_model: str,
    ocr_mode: str,
    page_range: str,
) -> list[dict]:
    """Build one dict row per source chunk with shared context fields."""
    rows = []
    for chunk in chunks:
        rows.append(
            {
                "question": question,
                "answer": answer,
                "pdf_name": chunk.get("pdf_name", "unknown.pdf"),
                "page_number": chunk.get("page_number", "n/a"),
                "chunk_id": chunk.get("chunk_id", "n/a"),
                "section": chunk.get("section", "Unbekannt"),
                "extraction_method": chunk.get("extraction_method", "pdf_text"),
                "score": _score(chunk),
                "text_excerpt": _excerpt(chunk.get("text", "")),
                "timestamp": timestamp,
                "embedding_model": embedding_model,
                "ocr_mode": ocr_mode,
                "page_range": page_range,
            }
        )
    return rows


def _score(chunk: dict) -> str:
    value = chunk.get("retrieval_score", chunk.get("score"))
    if isinstance(value, (int, float)) and float(value) > 0:
        return f"{float(value):.2f}"
    return ""


def to_csv(rows: list[dict]) -> str:
    """Serialize rows to CSV text."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def excel_available() -> bool:
    try:
        import openpyxl  # noqa: F401

        return True
    except ImportError:
        return False


def to_excel(rows: list[dict]) -> bytes | None:
    """Serialize rows to an .xlsx workbook. Returns None if openpyxl is missing."""
    try:
        from openpyxl import Workbook
    except ImportError:
        return None

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sources"
    worksheet.append(EXPORT_COLUMNS)
    for row in rows:
        worksheet.append([row.get(column, "") for column in EXPORT_COLUMNS])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
