# Research Paper Discovery Agent

An AI-assisted scientific literature discovery system with live paper search,
transparent ranking, PDF-RAG, optional OCR, source-grounded question answering,
local research memory, and multi-format export.

The application is designed for early literature exploration. It helps users
find, compare, and inspect relevant research, but it does not replace reading,
evaluating, and citing the original publications.

## Project Links

- Repository: [Amaniaslim/research-paper-discovery-agent](https://github.com/Amaniaslim/research-paper-discovery-agent)
- Final application entrypoint: `app_sprint3.py`
- Portfolio website source: [`docs/index.html`](docs/index.html)
- Container image target: `ghcr.io/amaniaslim/research-paper-discovery-agent:latest`

GitHub Pages has to be enabled for the `docs/` folder before the portfolio
website is public. No Streamlit Community Cloud URL or published container image
is claimed until the corresponding deployment exists.

## Main Features

- Live arXiv search with Semantic Scholar as a secondary live source
- Local cache and embedded offline fallback for resilient operation
- Metadata normalization and title/URL-based deduplication
- Transparent rule-based relevance ranking
- Abstract summaries generated locally or optionally improved with SAIA
- PDF upload and page-wise text extraction with PyMuPDF
- Whole-document or selected page-range indexing for large PDFs
- Optional Tesseract and Baidu Unlimited-OCR adapters
- Overlapping chunks with PDF, page, section, and extraction metadata
- ChromaDB storage with a JSON fallback
- Configurable Top-K retrieval and neighboring-chunk context
- Source-grounded answers with a no-key local fallback
- Local research memory and reopenable session history
- Markdown, CSV, and Excel exports
- Docker and Streamlit Community Cloud deployment support

## How the Agent Works

```text
Research question
    |
    +--> arXiv --> Semantic Scholar --> cache --> offline papers
    |       |
    |       +--> normalize --> deduplicate --> rank --> summarize
    |
    +--> selected PDFs --> extract/OCR --> chunk --> embed --> store
                                                    |
Question about PDFs --> Top-K retrieval + neighbors + section filter
                                                    |
                               SAIA answer or local source-based fallback
                                                    |
                                  sources + memory + MD/CSV/XLSX export
```

Every network-dependent capability has a local fallback. SAIA is optional, and
normal text-PDF workflows do not require OCR.

## Paper Discovery Workflow

1. Open **Paper Search** and enter a research question.
2. Choose the number of results and whether live search is enabled.
3. The agent queries arXiv, then Semantic Scholar when needed.
4. Results are normalized, deduplicated, filtered, and ranked.
5. Each ranked paper shows the signals that contributed to its score.
6. Abstract summaries are created heuristically unless SAIA is configured.
7. The run is saved to local memory and can be exported as Markdown.

If live services fail or return no useful papers, the agent uses a local cache
and then a small embedded offline dataset. This is an intentional resilience
feature, not an error state.

## PDF-RAG Workflow

1. Open **PDF Knowledge Base** and upload one or more PDFs.
2. Select the files and choose the whole document or a page range.
3. Configure chunking and optionally enable OCR for scanned pages.
4. Build the index in ChromaDB or the JSON fallback.
5. Ask a question, select Top-K, neighboring context, and optional sections.
6. Inspect the answer and its source cards.
7. Export the result and sources as Markdown, CSV, or Excel.

Source cards include the PDF name, page number, chunk ID, detected section,
extraction method, retrieval score, and original excerpt. Answers are limited to
retrieved content and should always be checked against the cited pages.

## Architecture

- `app_sprint3.py` is the combined Streamlit product UI.
- `paper_research_agent.py` handles live retrieval, fallbacks, normalization,
  ranking, optional SAIA summaries, caching, and review export.
- `review_core.py` provides paper/review data models, baseline ranking,
  clustering, heuristic summaries, and offline papers.
- `pdf_loader.py` extracts selected PDF pages and delegates optional OCR.
- `chunking.py` creates overlapping chunks while retaining source metadata.
- `embedding_config.py` selects a sentence-transformers model or the local
  deterministic lexical embedding.
- `rag_store.py` persists/query chunks with ChromaDB and JSON fallback.
- `rag_retriever.py` performs Top-K retrieval, section filtering, and neighboring
  context expansion.
- `rag_answer.py` produces a SAIA answer when configured or a local answer from
  retrieved chunks.
- `memory_store.py` and `history_store.py` provide local memory and session
  history.
- `export_utils.py` creates source tables for CSV and Excel.
- `src/ocr_service.py` isolates Tesseract and Unlimited-OCR integrations.

More detail is available in [docs/architecture.md](docs/architecture.md).

## Local Setup

Python 3.12 is recommended.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app_sprint3.py
```

### macOS or Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app_sprint3.py
```

Open `http://localhost:8501`. No API key is required for the offline paper
fallback, local embeddings, or source-based PDF answers.

## Docker Compose

The Docker image uses Python 3.12 and starts `app_sprint3.py`.

```bash
docker compose config --quiet
docker compose build
docker compose up -d
```

Open `http://localhost:8501` or check:

```bash
curl http://localhost:8501/_stcore/health
```

Stop the application with:

```bash
docker compose down
```

Compose persists `data/pdfs/` and `demo_output/`. Keep uploaded private PDFs and
runtime stores out of Git.

## Published Docker Image

The configured publication target is:

```text
ghcr.io/amaniaslim/research-paper-discovery-agent:latest
```

`docker-compose.yml` tags local builds with that name. The package must be
published to GitHub Container Registry before it can be pulled publicly; this
repository does not claim that publication has already happened.

## Configuration

Copy `.env.example` to `.env` for local use. `.env` is ignored and must never be
committed.

| Variable | Purpose | Default |
|---|---|---|
| `SAIA_API_KEY` | Optional SAIA summaries and PDF answers | empty |
| `SAIA_BASE_URL` | OpenAI-compatible SAIA endpoint | `https://chat-ai.academiccloud.de/v1` |
| `SAIA_MODEL` | SAIA text model | `mistral-large-3-675b-instruct-2512` |
| `ENABLE_LLM_SUMMARIES` | Enable SAIA summaries when a key exists | `true` |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional higher Semantic Scholar limits | empty |
| `EMBEDDING_MODEL` | `local` or a sentence-transformers model | `local` |
| `OCR_MODE` | `disabled`, `tesseract`, or `unlimited_ocr` | `disabled` |
| `UNLIMITED_OCR_BASE_URL` | Optional Unlimited-OCR HTTP endpoint | empty |
| `UNLIMITED_OCR_MODEL` | Unlimited-OCR model identifier | `Unlimited-OCR` |
| `UNLIMITED_OCR_API_KEY` | Optional OCR endpoint credential | empty |
| `UNLIMITED_OCR_PATH` | Optional local OCR command template | empty |

When `EMBEDDING_MODEL` names a sentence-transformers model but the package or
model is unavailable, the application falls back to the local embedding. Rebuild
an existing PDF index after changing embedding models.

## OCR Support

OCR is only attempted for pages with little or no extractable text.

- **Disabled:** scanned pages remain empty; text PDFs continue normally.
- **Tesseract:** requires `pytesseract`, Pillow, and a local Tesseract binary.
- **Unlimited-OCR:** uses either an OpenAI-compatible endpoint configured through
  `UNLIMITED_OCR_BASE_URL` or a local command containing the `{image}`
  placeholder in `UNLIMITED_OCR_PATH`.

A missing or failing OCR backend is handled without crashing normal text-PDF
workflows. See [docs/limitations.md](docs/limitations.md) for operational limits.

## Memory and Exports

Completed discovery runs are stored in ChromaDB when available and in JSON
otherwise. Lightweight session snapshots allow previous searches and PDF
questions to be reopened from the sidebar.

The product exports:

- a combined Markdown report with ranked papers, answer, and sources;
- CSV source rows with question, answer, page, chunk, score, and configuration;
- Excel source rows with the same fields.

All generated files are local runtime data under `demo_output/` and are ignored
by Git.

## Tests

Install development dependencies and run the complete checks:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe demo_smoke_check.py
.\.venv\Scripts\python.exe -m compileall .
.\.venv\Scripts\python.exe -m ruff check .
```

The automated suite covers ranking, offline retrieval, PDF chunk metadata,
section filtering, local embeddings, source-based answers, and Markdown export.

## Project Structure

```text
research-paper-discovery-agent/
|-- app_sprint3.py          # Final combined Streamlit application
|-- app.py                  # Legacy paper-search-only entrypoint
|-- paper_research_agent.py
|-- review_core.py
|-- pdf_loader.py
|-- chunking.py
|-- embedding_config.py
|-- rag_store.py
|-- rag_retriever.py
|-- rag_answer.py
|-- memory_store.py
|-- history_store.py
|-- export_utils.py
|-- src/
|   `-- ocr_service.py
|-- tests/
|-- docs/                   # Portfolio website and technical documentation
|-- scripts/
|   `-- create_final_zip.py
|-- data/
|   `-- pdfs/               # Local uploads; PDFs are ignored
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
|-- .env.example
`-- LICENSE
```

## Important Limitations

- Ranking is transparent and rule-based rather than learned.
- Heuristic summaries are derived from titles and abstracts.
- The local embedding prioritizes resilience over state-of-the-art semantic
  retrieval quality.
- OCR quality and speed depend on an external backend and document quality.
- Large PDFs require more time and storage; page-range indexing is recommended.
- Source-grounded generation can still be incomplete because it only receives
  retrieved chunks.
- Results support exploration, not final academic or scientific judgment.

## Streamlit Community Cloud

Deployment settings:

- Repository: `Amaniaslim/research-paper-discovery-agent`
- Branch: `main`
- Main file: `app_sprint3.py`
- Recommended Python: `3.12`

Optional secrets can be added in the Streamlit deployment settings:

```toml
SAIA_API_KEY = "..."
SAIA_BASE_URL = "https://chat-ai.academiccloud.de/v1"
SAIA_MODEL = "mistral-large-3-675b-instruct-2512"
ENABLE_LLM_SUMMARIES = "true"
SEMANTIC_SCHOLAR_API_KEY = "..."
EMBEDDING_MODEL = "local"
OCR_MODE = "disabled"
```

Do not commit `.streamlit/secrets.toml`. Missing SAIA, Semantic Scholar, or OCR
credentials do not prevent the base application from starting.
