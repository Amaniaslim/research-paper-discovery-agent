from __future__ import annotations

import chunking


def test_chunk_pages_preserves_source_metadata() -> None:
    pages = [
        {
            "pdf_name": "paper.pdf",
            "page_number": 3,
            "text": "Agentic AI security risk " * 80,
        }
    ]

    chunks = chunking.chunk_pages(pages, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert chunks[0]["pdf_name"] == "paper.pdf"
    assert chunks[0]["page_number"] == 3
    assert chunks[0]["chunk_id"].startswith("p3-c")
    assert chunks[0]["text"]


def test_chunk_pages_skips_empty_text() -> None:
    chunks = chunking.chunk_pages(
        [{"pdf_name": "empty.pdf", "page_number": 1, "text": "   "}],
    )

    assert chunks == []
