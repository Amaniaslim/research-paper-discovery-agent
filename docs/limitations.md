# Limitations

## Retrieval and Ranking

- Live search depends on arXiv and Semantic Scholar availability and rate limits.
- The local offline dataset is intentionally small and focused on the project
  topic.
- Ranking is transparent and rule-based, so it may miss papers that use
  unexpected terminology.

## PDF-RAG

- Source-grounded answers are limited to the retrieved chunks and may omit
  relevant content elsewhere in a document.
- The default local lexical embedding favors reliability and low resource usage
  over advanced semantic matching.
- Changing embedding models requires rebuilding the stored index.
- Page ranges improve scalability but intentionally exclude unselected pages.

## OCR

- OCR is implemented as an optional adapter, not a bundled guaranteed service.
- Tesseract requires a system binary in addition to Python packages.
- Unlimited-OCR requires a separately operated endpoint or CLI.
- Scans with complex layouts, handwriting, or low resolution may produce poor
  text even when an OCR backend is available.

## Academic Use

- Abstract summaries and generated answers can be incomplete or inaccurate.
- The system supports early discovery; it does not replace critical reading,
  source verification, citation management, or scientific judgment.
