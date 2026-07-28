from __future__ import annotations

import chunking
import pdf_loader


def test_chunk_pages_preserves_source_metadata() -> None:
    pages = [
        {
            "pdf_name": "paper.pdf",
            "page_number": 3,
            "section": "Methods",
            "extraction_method": "ocr",
            "text": "Agentic AI security risk " * 80,
        }
    ]

    chunks = chunking.chunk_pages(pages, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert chunks[0]["pdf_name"] == "paper.pdf"
    assert chunks[0]["page_number"] == 3
    assert chunks[0]["chunk_id"].startswith("p3-c")
    assert chunks[0]["section"] == "Methods"
    assert chunks[0]["extraction_method"] == "ocr"
    assert chunks[0]["text"]


def test_chunk_pages_skips_empty_text() -> None:
    chunks = chunking.chunk_pages(
        [{"pdf_name": "empty.pdf", "page_number": 1, "text": "   "}],
    )

    assert chunks == []


def test_unlimited_ocr_without_endpoint_returns_empty(monkeypatch) -> None:
    monkeypatch.delenv("UNLIMITED_OCR_BASE_URL", raising=False)

    assert pdf_loader._ocr_page(object(), provider="unlimited_ocr") == ""


def test_extract_pdf_pages_respects_inclusive_page_range(tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "three-pages.pdf"
    document = fitz.open()
    for page_number in range(1, 4):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {page_number} contains searchable research text.")
    document.save(pdf_path)
    document.close()

    pages = pdf_loader.extract_pdf_pages(pdf_path, page_start=2, page_end=3)

    assert [page["page_number"] for page in pages] == [2, 3]
    assert "Page 2" in pages[0]["text"]
    assert "Page 3" in pages[1]["text"]
