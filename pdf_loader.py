from __future__ import annotations

from pathlib import Path


def extract_pdf_pages(pdf_path: Path) -> list[dict]:
    """Extract page-wise text from a PDF with PyMuPDF."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF text extraction. Install pymupdf.") from exc

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported: {pdf_path.name}")

    pages: list[dict] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            pages.append(
                {
                    "pdf_name": pdf_path.name,
                    "page_number": index,
                    "text": text,
                }
            )
    return pages


def save_uploaded_pdf(uploaded_file, target_dir: Path) -> Path:
    """Persist a Streamlit uploaded PDF in the configured PDF directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(uploaded_file.name)
    target_path = target_dir / safe_name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def _safe_filename(name: str) -> str:
    keep = [char if char.isalnum() or char in {".", "-", "_", " "} else "_" for char in name]
    safe = "".join(keep).strip().replace(" ", "_")
    return safe or "uploaded.pdf"
