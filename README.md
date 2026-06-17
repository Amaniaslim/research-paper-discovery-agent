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
  - page-wise text extraction with PyMuPDF
  - text chunking with page metadata
  - ChromaDB chunk storage with JSON fallback
  - chunk retrieval for user questions
  - optional SAIA answer generation
  - fallback answer from retrieved chunks
  - source display with PDF name and page number

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

PDF-RAG prototype. The agent uploads PDFs, extracts page-wise text, chunks the
text, stores chunks in ChromaDB, retrieves relevant chunks for a question, and
generates an answer with PDF name and page references. LLM answer generation is
optional and falls back to retrieved chunks if no API key is configured.

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

## Environment Variables

Copy `.env.example` to `.env` and add your own keys if needed.

```env
SAIA_API_KEY=your_api_key_here
SEMANTIC_SCHOLAR_API_KEY=optional_key_here
```

No API key is required for the offline fallback demo. Do not commit `.env`.

## Project Structure

```text
research-paper-discovery-agent/
|-- app.py
|-- app_sprint3.py
|-- paper_research_agent.py
|-- review_core.py
|-- memory_store.py
|-- pdf_loader.py
|-- chunking.py
|-- rag_store.py
|-- rag_retriever.py
|-- rag_answer.py
|-- data/
|   `-- pdfs/
|-- demo_output/
|-- docs/
|-- tests/
|-- requirements.txt
|-- .env.example
`-- .gitignore
```

The files currently remain at repository root to keep the existing sprint apps
simple and executable. A future refactor can move core modules into `src/`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Additional smoke check:

```powershell
.\.venv\Scripts\python.exe .\demo_smoke_check.py
```

## Limitations

- PDF-RAG works best with text-based PDFs.
- Scanned PDFs are not supported yet because OCR is not implemented.
- Ranking is transparent and rule-based, not ML-based.
- Local embeddings are simple and deterministic for demo stability.
- Real semantic embeddings are future work.
- LLM answer generation depends on API configuration.
- The agent supports early literature exploration, not final scientific judgment.

See [docs/limitations.md](docs/limitations.md) for more detail.

## Future Work

- Dedicated semantic embedding API
- OCR for scanned PDFs
- Better citation and bibliography extraction
- Stronger evaluation tests for retrieval quality
- Optional APA/BibTeX export polish
- Refactor core modules into a `src/` package
