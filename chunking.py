from __future__ import annotations


def chunk_pages(
    pages: list[dict],
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[dict]:
    """Split extracted page text into overlapping chunks with source metadata."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size.")

    chunks: list[dict] = []
    for page in pages:
        text = " ".join((page.get("text") or "").split())
        if not text:
            continue

        start = 0
        chunk_index = 1
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(
                    {
                        "pdf_name": page["pdf_name"],
                        "page_number": page["page_number"],
                        "chunk_id": f"p{page['page_number']}-c{chunk_index}",
                        "text": chunk_text,
                    }
                )
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
            chunk_index += 1
    return chunks
