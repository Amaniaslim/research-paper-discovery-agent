from __future__ import annotations

import re
import sys
from pathlib import Path

# Make the ``src`` package importable regardless of how the app is launched.
_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from src import ocr_service  # noqa: E402


def pdf_page_count(pdf_path: Path) -> int:
    """Return the number of pages in a PDF (0 if it cannot be opened)."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF text extraction. Install pymupdf.") from exc
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    try:
        with fitz.open(pdf_path) as document:
            return document.page_count
    except Exception:
        return 0


def is_scanned_pdf(pdf_path: Path, sample_pages: int = 5, min_chars: int = 40) -> bool:
    """Heuristic: True when the first sampled pages contain no extractable text.

    Used to detect scanned PDFs that need OCR before indexing.
    """
    try:
        import fitz
    except ImportError:
        return False
    if not pdf_path.exists():
        return False
    try:
        with fitz.open(pdf_path) as document:
            checked = 0
            for page in document:
                if checked >= sample_pages:
                    break
                if len(page.get_text("text").strip()) >= min_chars:
                    return False
                checked += 1
        return checked > 0
    except Exception:
        return False


def extract_pdf_pages(
    pdf_path: Path,
    enable_ocr: bool = False,
    ocr_min_chars: int = 40,
    ocr_provider: str = "tesseract",
    page_start: int | None = None,
    page_end: int | None = None,
) -> list[dict]:
    """Extract page-wise text from a PDF with optional OCR for scanned pages.

    ``page_start``/``page_end`` are 1-based, inclusive. When omitted the whole
    PDF is processed. This keeps large PDFs (>100 pages) manageable: only the
    selected page range is extracted, chunked, and indexed.
    """
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for PDF text extraction. Install pymupdf.") from exc

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Only PDF files are supported: {pdf_path.name}")

    pages: list[dict] = []
    current_section = "Unbekannt"
    ocr_attempted = False
    with fitz.open(pdf_path) as document:
        total = document.page_count
        start = max(1, page_start or 1)
        end = min(total, page_end or total)
        for index in range(start, end + 1):
            page = document[index - 1]
            text = page.get_text("text").strip()
            extraction_method = "pdf_text"
            if enable_ocr and len(text) < ocr_min_chars:
                ocr_attempted = True
                ocr_text = _ocr_page(page, provider=ocr_provider).strip()
                if ocr_text:
                    text = ocr_text
                    extraction_method = f"ocr_{ocr_service.normalize_provider(ocr_provider)}"
            current_section = _detect_section(text, current_section)
            pages.append(
                {
                    "pdf_name": pdf_path.name,
                    "page_number": index,
                    "text": text,
                    "section": current_section,
                    "extraction_method": extraction_method,
                }
            )
    if enable_ocr and ocr_attempted and not any(page["extraction_method"].startswith("ocr_") for page in pages):
        if not any(page["text"] for page in pages):
            raise RuntimeError(
                "OCR was requested, but no OCR text could be extracted. "
                "Use local Tesseract or configure an Unlimited-OCR compatible server."
            )
    return pages


def save_uploaded_pdf(uploaded_file, target_dir: Path) -> Path:
    """Persist a Streamlit uploaded PDF in the configured PDF directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(uploaded_file.name)
    target_path = target_dir / safe_name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def tesseract_available() -> bool:
    return ocr_service.tesseract_available()


def _safe_filename(name: str) -> str:
    keep = [char if char.isalnum() or char in {".", "-", "_", " "} else "_" for char in name]
    safe = "".join(keep).strip().replace(" ", "_")
    return safe or "uploaded.pdf"


def _ocr_page(page, provider: str) -> str:
    """Render a PDF page to PNG and hand it to the OCR adapter.

    Short-circuits to an empty string when the selected OCR backend is not
    available, so we never rasterize a page we cannot OCR.
    """
    if not ocr_service.provider_available(provider):
        return ""
    try:
        import fitz
    except ImportError:
        return ""
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    return ocr_service.ocr_image_bytes(pixmap.tobytes("png"), provider=provider)


def _detect_section(text: str, fallback: str) -> str:
    for raw_line in text.splitlines()[:18]:
        line = " ".join(raw_line.strip().split())
        if not line or len(line) > 90:
            continue
        normalized = re.sub(r"^\d+(?:\.\d+)*\s*", "", line).strip().lower()
        for label, patterns in _SECTION_PATTERNS:
            if normalized in patterns or any(normalized.startswith(pattern) for pattern in patterns):
                return label
    return fallback


_SECTION_PATTERNS = (
    ("Abstract", {"abstract"}),
    ("Introduction", {"introduction", "einleitung"}),
    ("Related Work", {"related work", "background", "literature review"}),
    ("Methods", {"method", "methods", "methodology", "approach", "materials and methods"}),
    ("Results", {"results", "experiments", "evaluation"}),
    ("Discussion", {"discussion"}),
    ("Limitations", {"limitations", "limitations and future work"}),
    ("Conclusion", {"conclusion", "conclusions", "concluding remarks"}),
    ("References", {"references", "bibliography"}),
)
