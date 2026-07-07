# Research Paper Discovery Agent

Sprint-based educational prototype for scientific literature discovery around
Agentic AI Security. The project helps users find papers, rank them, summarize
abstracts, remember previous research runs, and ask source-grounded questions
against uploaded PDF full texts.

The agent supports the first research overview. It does not replace reading,
evaluating, or citing scientific papers carefully.

## Features

- Streamlit demo UI for Sprint 2 and Sprint 3 workflows
- Offline demo data for stable Sprint 1 fallback behavior
- Live paper search via arXiv with Semantic Scholar fallback
- Local cache and embedded demo-paper fallback for reliable demos
- Metadata normalization and deduplication
- Transparent rule-based ranking
- Abstract-based heuristic summaries, with optional SAIA summaries
- ChromaDB memory with JSON fallback
- Markdown export for literature-review results
- Sprint 3 PDF-RAG prototype:
  - PDF upload
  - page-wise text extraction with PyMuPDF and optional OCR fallback
  - large-PDF handling: index the whole PDF or only a selected page range
  - text chunking with page, section, and extraction metadata
  - ChromaDB chunk storage with JSON fallback
  - configurable Top-K retrieval (default 5) with optional neighboring-chunk
    context expansion (0/1/2 adjacent chunks on the same page)
  - pluggable embedding configuration with a safe offline fallback
  - OCR adapter (`src/ocr_service.py`) with a scanned-PDF detector and support
    for Baidu Unlimited-OCR (HTTP endpoint or local CLI)
  - optional SAIA answer generation, with fallback answer from retrieved chunks
  - source display with PDF name, page number, chunk ID, section, and extraction method
  - Markdown export plus CSV and Excel export of retrieved sources
  - scalability log (pages, chunks, indexing time, retrieval time)
  - Docker / docker-compose support

## Sprint Overview

### Sprint 1

Offline MVP with saved paper data, research-question input, paper ranking,
abstract summaries, ChromaDB memory, and Markdown export. The goal was a stable
and reproducible demo without API or network risk.

### Sprint 2

Live Search & Retrieve workflow. The agent queries arXiv, falls back to Semantic
Scholar, then falls back to local cache or demo data. It normalizes fields,
deduplicates papers, ranks them transparently, stores research runs in memory,
and exports a Markdown review.

### Sprint 3

PDF-RAG prototype. The agent uploads PDFs, extracts page-wise text with optional
OCR fallback, chunks the text, stores chunks in ChromaDB, retrieves relevant
chunks for a question, and generates an answer with PDF name, page, chunk, and
section references. LLM answer generation is optional and falls back to retrieved
chunks if no API key is configured.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

Sprint 2 app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

Sprint 3 PDF-RAG app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app_sprint3.py
```

If port `8501` is already used:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app_sprint3.py --server.port 8502
```

Command-line Sprint 2 review:

```powershell
.\.venv\Scripts\python.exe .\paper_research_agent.py --offline
```

The app runs fully locally without Docker. Docker is an optional deployment path.

## PDF-RAG Workflow

1. Upload one or more PDFs in the **PDF-RAG Demo** tab (saved to `data/pdfs/`).
2. Configure the index: choose PDFs, page range, chunk size/overlap, and OCR.
3. Build the index (chunks are stored in ChromaDB, JSON fallback otherwise).
4. Ask a question. Choose Top-K and optional context expansion.
5. Read the grounded answer and inspect the source cards (PDF, page, chunk,
   section, excerpt).
6. Export the result as Markdown, CSV, or Excel in the **Export & Memory** tab.

## Large PDFs and Page Ranges

Before indexing you can choose to analyze the whole PDF or only a page range:

- **Analyze whole PDF** — extract, chunk, and index every page.
- **Analyze only a page range** — e.g. start page `1`, end page `20`. Only the
  selected pages are extracted, chunked, and indexed.

PDFs with more than 100 pages show a performance warning and default to the
page-range option. Index statistics show the number of PDFs, selected pages,
chunks, storage backend, embedding model, OCR mode, and indexing time. A simple
scalability log is appended to `demo_output/scalability_log.csv` (pages, chunks,
indexing time, and retrieval time).

## OCR Support and Unlimited-OCR

Scanned PDFs have no extractable text. The app detects this and shows a hint that
OCR is required. OCR is optional and controlled by the `OCR_MODE` environment
variable (`disabled`, `tesseract`, or `unlimited_ocr`).

OCR handling lives in `src/ocr_service.py`, so backends are isolated from the
rest of the app:

- **Tesseract (local)** — needs `pytesseract` plus a local Tesseract binary.
- **Baidu Unlimited-OCR** — following the professor feedback
  (https://github.com/baidu/Unlimited-OCR). Unlimited-OCR runs as a separate
  server/CLI. Configure it via environment variables (no hardcoded paths):
  - `UNLIMITED_OCR_BASE_URL` — an OpenAI-compatible endpoint (vLLM/SGLang), or
  - `UNLIMITED_OCR_PATH` — a local CLI command, using `{image}` as the page-image
    placeholder, e.g. `python /opt/Unlimited-OCR/run.py --image {image}`.

If OCR is enabled but the backend is not available, the app shows a helpful
warning and keeps running. Normal text PDFs work without any OCR setup.

## Run with Docker

The app can run as a Docker container. It exposes port `8501` and stores data in
mounted volumes so uploaded PDFs, exports, and the ChromaDB/memory stores persist
across runs.

Build and run with plain Docker:

```bash
docker build -t research-paper-discovery-agent .
docker run -p 8501:8501 research-paper-discovery-agent
```

Or use docker-compose (recommended, wires up volumes and environment):

```bash
docker compose up --build
```

Then open http://localhost:8501.

To pass configuration, set the variables in your shell or a `.env` file that
docker-compose reads automatically, for example:

```env
SAIA_API_KEY=your_api_key_here
OCR_MODE=tesseract
EMBEDDING_MODEL=local
UNLIMITED_OCR_PATH=
```

## Environment Variables

Copy `.env.example` to `.env` and add your own keys if needed.

```env
# LLM answer generation (optional)
SAIA_API_KEY=your_api_key_here
SAIA_BASE_URL=https://chat-ai.academiccloud.de/v1
SAIA_MODEL=mistral-large-3-675b-instruct-2512
ENABLE_LLM_SUMMARIES=true

# Live paper search (optional)
SEMANTIC_SCHOLAR_API_KEY=optional_key_here

# Retrieval embeddings: "local" (offline default) or a sentence-transformers model
EMBEDDING_MODEL=local

# OCR: disabled | tesseract | unlimited_ocr
OCR_MODE=disabled
UNLIMITED_OCR_BASE_URL=
UNLIMITED_OCR_PATH=
```

No API key is required for the offline fallback demo. Do not commit `.env`.

## Project Structure

```text
research-paper-discovery-agent/
|-- app.py                  # Sprint 2 app
|-- app_sprint3.py          # Sprint 3 PDF-RAG app (main)
|-- paper_research_agent.py
|-- review_core.py
|-- memory_store.py
|-- pdf_loader.py           # PDF extraction, page ranges, scanned detection
|-- chunking.py
|-- rag_store.py            # ChromaDB storage + JSON fallback
|-- rag_retriever.py        # Top-K retrieval + neighbor context expansion
|-- rag_answer.py
|-- embedding_config.py     # Pluggable embeddings with safe local fallback
|-- export_utils.py         # CSV / Excel export of sources
|-- src/
|   `-- ocr_service.py      # OCR adapter (Tesseract / Unlimited-OCR)
|-- data/
|   `-- pdfs/
|-- demo_output/            # exports, ChromaDB stores, scalability log
|-- docs/
|-- tests/
|-- Dockerfile
|-- .dockerignore
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
`-- .gitignore
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Additional smoke check:

```powershell
.\.venv\Scripts\python.exe .\demo_smoke_check.py
```

## Known Limitations

- OCR depends on an external setup: local Tesseract, or a separately started
  Baidu Unlimited-OCR server/CLI configured via environment variables.
- Very large PDFs may take longer to extract, chunk, and index. Use the page
  range option to keep indexing fast.
- Retrieval quality depends on the embedding model and chunking settings. The
  default embedding is a deterministic offline lexical embedding for demo
  stability; a sentence-transformers model can be enabled via `EMBEDDING_MODEL`.
  Switching the embedding model requires rebuilding the index.
- Generated answers must be checked by the user. The agent supports early
  literature exploration, not final scientific judgment.
- Ranking is transparent and rule-based, not ML-based.
- LLM answer generation depends on API configuration; without a key the app uses
  a fallback answer built from retrieved chunks.

See [docs/limitations.md](docs/limitations.md) for more detail.

## Next Steps

- Dedicated semantic embedding API / stronger default embeddings
- Stronger OCR setup and scanned-PDF evaluation with Unlimited-OCR
- Better citation and bibliography extraction
- Stronger evaluation tests for retrieval quality
- Optional APA/BibTeX export polish
