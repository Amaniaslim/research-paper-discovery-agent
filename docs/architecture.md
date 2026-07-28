# Architecture

The Research Paper Discovery Agent combines two workflows in one Streamlit
entrypoint, `app_sprint3.py`: live literature discovery and source-grounded
question answering over uploaded PDFs.

## Paper Discovery

1. `paper_research_agent.py` expands and submits a research query.
2. arXiv is tried first, followed by Semantic Scholar.
3. Local cache and embedded papers provide an offline fallback.
4. Records are normalized, deduplicated, filtered, and ranked.
5. `review_core.py` creates heuristic summaries; SAIA can replace individual
   summaries when configured.
6. `memory_store.py` and `history_store.py` persist local research context.

## PDF Knowledge Base

1. `pdf_loader.py` saves PDFs and extracts selected pages with PyMuPDF.
2. `src/ocr_service.py` optionally processes scanned pages with Tesseract or
   Unlimited-OCR.
3. `chunking.py` creates overlapping chunks with page and section metadata.
4. `embedding_config.py` chooses the local embedding or an optional
   sentence-transformers model.
5. `rag_store.py` writes chunks to ChromaDB or JSON.
6. `rag_retriever.py` performs Top-K retrieval, filtering, and neighboring-chunk
   expansion.
7. `rag_answer.py` asks SAIA when configured or builds an answer from retrieved
   chunks.
8. `export_utils.py` creates CSV and Excel source exports.

## Resilience Boundaries

- Network search, SAIA, semantic embeddings, OCR, and ChromaDB are independently
  optional.
- A failure in one optional integration falls back locally instead of disabling
  the whole application.
- Uploaded PDFs and runtime stores remain local and are excluded from Git and
  release archives.
