# Architecture

The project is organized as a small Streamlit prototype with separate modules for
paper discovery, memory, and PDF-RAG.

## Main Apps

- `app.py`: Sprint 2 Streamlit app for live paper search, ranking, memory, and
  Markdown export.
- `app_sprint3.py`: Sprint 3 Streamlit app that keeps the discovery workflow and
  adds PDF upload, indexing, retrieval, answering, sources, memory, and export.

## Discovery Workflow

- `paper_research_agent.py`: live retrieval, fallback logic, normalization,
  ranking, summaries, cache, and exports.
- `review_core.py`: shared data classes, demo papers, baseline ranking,
  clustering, and Markdown generation.
- `memory_store.py`: ChromaDB memory with JSON fallback.

## PDF-RAG Workflow

- `pdf_loader.py`: saves uploaded PDFs and extracts page-wise text with PyMuPDF.
- `chunking.py`: splits page text into overlapping chunks while preserving PDF
  name, page number, and chunk ID.
- `rag_store.py`: stores chunks in ChromaDB or JSON fallback and provides local
  deterministic embeddings for stable demos.
- `rag_retriever.py`: retrieves relevant chunks with ChromaDB or keyword fallback.
- `rag_answer.py`: generates source-grounded answers with SAIA when configured,
  or returns a fallback answer from retrieved chunks.

## Runtime Data

Generated data is written to `demo_output/` and uploaded PDFs are stored in
`data/pdfs/`. These runtime artifacts are ignored by Git.
