# Research Paper Discovery Agent

An AI-assisted research application for discovering scientific papers,
explaining transparent relevance rankings, and asking source-grounded questions
about uploaded PDFs.

The application combines live literature search with resilient offline
fallbacks, PDF extraction and optional OCR, retrieval-augmented generation
(RAG), local research memory, and Markdown/CSV/Excel exports.

## Project Links

- **Code repository:** [github.com/Amaniaslim/research-paper-discovery-agent](https://github.com/Amaniaslim/research-paper-discovery-agent)
- **Live application:** [research-paper-discovery-agent…streamlit.app](https://research-paper-discovery-agent-bysmydwzhs4nepreseaurt.streamlit.app/)
- **Live portfolio:** [amaniaslim.github.io/research-paper-discovery-agent](https://amaniaslim.github.io/research-paper-discovery-agent/)
- **Container package:** [GHCR package](https://github.com/users/Amaniaslim/packages/container/package/research-paper-discovery-agent)
- **Demo Day presentation:** [Research Paper Discovery Agent (PDF)](docs/assets/Research_Paper_Discovery_Agent_Demo_Day.pdf)
- **Full Git history:** [commits on `main`](https://github.com/Amaniaslim/research-paper-discovery-agent/commits/main/)
- **License:** [MIT](LICENSE)

The GitHub Pages portfolio is published from `docs/`. The container image is
published to GHCR as `ghcr.io/amaniaslim/research-paper-discovery-agent` with
the tags `latest` and `sha-1723fef`. The package is currently private.

## Features

- Live arXiv search with Semantic Scholar as a secondary source
- Cache and embedded offline papers for resilient demonstrations
- Metadata normalization, deduplication, and transparent rule-based ranking
- Local heuristic summaries with optional SAIA-generated summaries
- PDF upload and page-aware text extraction with PyMuPDF
- Whole-document or selected page-range indexing
- Optional Tesseract and Unlimited-OCR integrations for scanned pages
- Overlapping chunks with PDF, page, section, and extraction metadata
- ChromaDB storage with a local JSON fallback
- Configurable Top-K retrieval, section filtering, and neighboring context
- Source-grounded answers with a no-key local fallback
- Reopenable local session history and research memory
- Markdown, CSV, and Excel exports

## System Overview

```text
Research question
    |
    +--> arXiv --> Semantic Scholar --> cache --> offline papers
    |       |
    |       +--> normalize --> deduplicate --> rank --> summarize
    |
    +--> selected PDFs --> extract/OCR --> chunk --> embed --> store
                                                    |
Question about PDFs --> retrieve + filter + neighboring context
                                                    |
                              SAIA or local source-based answer
                                                    |
                                  sources + memory + export
```

Every network-dependent feature has a local fallback. API keys are optional for
the standard offline discovery and source-based PDF workflows.

## Setup Instructions

### Prerequisites

- Git
- Python 3.12
- An internet connection for dependency installation
- Docker Desktop or Docker Engine with Compose, only for container deployment
- Optional: a local Tesseract installation when using `OCR_MODE=tesseract`

### 1. Clone the repository

```bash
git clone https://github.com/Amaniaslim/research-paper-discovery-agent.git
cd research-paper-discovery-agent
```

### 2. Create the virtual environment and install dependencies

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

#### macOS or Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Configure optional integrations

The application works without secrets. To configure SAIA, Semantic Scholar, a
different embedding model, or OCR, create a local `.env` file:

#### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

#### macOS or Linux

```bash
cp .env.example .env
```

Edit `.env` as required. Never commit `.env` or credentials.

### 4. Start the application

#### Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

#### macOS or Linux

```bash
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501). Stop the server with
`Ctrl+C`.

## Docker and Docker Compose Deployment

The included `Dockerfile` uses Python 3.12, installs optional local Tesseract
support, exposes port `8501`, and defines a Streamlit health check.

### Docker Compose

From the repository root:

```bash
docker compose config --quiet
docker compose up --build -d
```

Open [http://localhost:8501](http://localhost:8501), then verify the health
endpoint:

```bash
curl http://localhost:8501/_stcore/health
```

Inspect logs or stop the deployment:

```bash
docker compose logs -f
docker compose down
```

Compose automatically reads an existing `.env` file. It mounts
`data/pdfs/` and `demo_output/` so uploaded PDFs, local indexes, memory, and
exports survive container recreation. These runtime files are ignored by Git.

### Published GHCR image

While the package is private, authenticate with a GitHub account that has
package access:

```bash
gh auth token | docker login ghcr.io --username Amaniaslim --password-stdin
docker pull ghcr.io/amaniaslim/research-paper-discovery-agent:latest
docker run --rm -p 8501:8501 ghcr.io/amaniaslim/research-paper-discovery-agent:latest
```

For a reproducible deployment, use the immutable commit tag:

```bash
docker pull ghcr.io/amaniaslim/research-paper-discovery-agent:sha-1723fef
```

If the package owner changes its visibility to public in GitHub Package
Settings, the login command is no longer required.

### Plain Docker

```bash
docker build -t research-paper-discovery-agent .
docker run --rm -p 8501:8501 --env-file .env research-paper-discovery-agent
```

Omit `--env-file .env` when no optional integrations are configured.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `SAIA_API_KEY` | Optional SAIA summaries and PDF answers | empty |
| `SAIA_BASE_URL` | OpenAI-compatible SAIA endpoint | `https://chat-ai.academiccloud.de/v1` |
| `SAIA_MODEL` | SAIA text model | `mistral-large-3-675b-instruct-2512` |
| `ENABLE_LLM_SUMMARIES` | Use SAIA summaries when a key is present | `true` |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional higher Semantic Scholar rate limits | empty |
| `EMBEDDING_MODEL` | `local` or a sentence-transformers model | `local` |
| `OCR_MODE` | `disabled`, `tesseract`, or `unlimited_ocr` | `disabled` |
| `UNLIMITED_OCR_BASE_URL` | Optional Unlimited-OCR HTTP endpoint | empty |
| `UNLIMITED_OCR_MODEL` | Unlimited-OCR model identifier | `Unlimited-OCR` |
| `UNLIMITED_OCR_API_KEY` | Optional OCR endpoint credential | empty |
| `UNLIMITED_OCR_PATH` | Optional local OCR command containing `{image}` | empty |

If an optional integration is unavailable, the application falls back locally
instead of disabling the full workflow.

## Usage

### Discover papers

1. Open **Paper Search**.
2. Enter a research question and select the desired result count.
3. Run the search and inspect the source status and ranking signals.
4. Review individual papers and heuristic or SAIA-generated summaries.
5. Save or export the result.

### Ask questions about PDFs

1. Open **PDF Knowledge Base** and upload one or more PDFs.
2. Select full-document or page-range indexing.
3. Configure chunking and optional OCR.
4. Build the index.
5. Ask a question and configure Top-K, neighboring context, and sections.
6. Verify the answer against the displayed PDF pages and excerpts.
7. Export the answer and source table.

## Tests and Quality Checks

Install development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run the automated tests and static checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\smoke_check.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall .
```

On macOS or Linux, replace `.\.venv\Scripts\python.exe` with `python`.

The suite covers ranking, offline retrieval, PDF chunk metadata, section
filtering, local embeddings, source-based answers, exports, history, and the
sanitized release archive.

## Project Structure

```text
research-paper-discovery-agent/
|-- app.py                    # Streamlit application entrypoint
|-- paper_research_agent.py   # Discovery pipeline and source fallbacks
|-- review_core.py            # Models, ranking, and local summaries
|-- pdf_loader.py             # Page-aware PDF extraction
|-- ocr_service.py            # Optional OCR integrations
|-- chunking.py               # Metadata-preserving text chunks
|-- embedding_config.py       # Local/optional embedding selection
|-- rag_store.py              # ChromaDB and JSON storage
|-- rag_retriever.py          # Retrieval, filtering, and context expansion
|-- rag_answer.py             # SAIA and local grounded answers
|-- memory_store.py           # Research memory
|-- history_store.py          # Reopenable sessions
|-- export_utils.py           # CSV and Excel exports
|-- tests/                    # Automated test suite
|-- scripts/
|   |-- create_final_zip.py   # Sanitized delivery archive builder
|   `-- smoke_check.py        # Offline end-to-end smoke check
|-- docs/
|   |-- assets/               # Public presentation assets
|   |-- sprints/              # Sprint 1-3 documentation
|   |-- architecture.md
|   |-- limitations.md
|   `-- index.html            # GitHub Pages portfolio
|-- data/
|   `-- pdfs/                 # Local PDF uploads; contents ignored by Git
|-- Dockerfile
|-- compose.yaml
|-- requirements.txt
|-- requirements-dev.txt
|-- pyproject.toml
|-- .env.example
`-- LICENSE
```

## Change History

This table covers the complete repository history up to and including the
current Streamlit deployment link. Detailed Sprint documentation is available in
[`docs/sprints/`](docs/sprints/), and every original diff remains available in
the linked Git history.

| Date | Revision | Change |
|---|---|---|
| 2026-07-29 | Current Streamlit deployment | Added the public Streamlit Community Cloud application to the repository documentation and portfolio. |
| 2026-07-29 | [`4ab4113`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/4ab4113) | Published the validated `linux/amd64` image as `latest` and `sha-1723fef`, linked it to the repository, and documented authenticated pulls. |
| 2026-07-29 | [`1723fef`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/1723fef) | Made `app.py` the single entrypoint, normalized Compose and script names, reorganized historical documentation, removed obsolete placeholders, and expanded setup/deployment documentation. |
| 2026-07-29 | [`4e79cb3`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/4e79cb3) | Added the live portfolio URL and GitHub Pages metadata. |
| 2026-07-29 | [`9937497`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/9937497) | Added and linked the Demo Day presentation. |
| 2026-07-29 | [`78516e7`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/78516e7) | Prepared the final university delivery, documentation, tests, Docker deployment, website, and sanitized archive. |
| 2026-07-07 | [`fb3296b`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/fb3296b) | Finalized the Research Paper Discovery Agent. |
| 2026-06-25 | [`7fb3335`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/7fb3335) | Added the Sprint 3 PDF-RAG improvements. |
| 2026-06-17 | [`75c32c0`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/75c32c0) | Improved export-status presentation. |
| 2026-06-17 | [`9a0baf2`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/9a0baf2) | Prioritized RAG retrieval controls in the interface. |
| 2026-06-17 | [`3bc8f8f`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/3bc8f8f) | Improved export and memory presentation. |
| 2026-06-17 | [`2f5c32c`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/2f5c32c) | Improved PDF-RAG answer style and source visibility. |
| 2026-06-17 | [`ec7771a`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/ec7771a) | Polished Sprint 3 user-interface text. |
| 2026-06-17 | [`502da32`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/502da32) | Prepared the Sprint 3 agent for its GitHub release. |
| 2026-06-11 | [`821b7d1`](https://github.com/Amaniaslim/research-paper-discovery-agent/commit/821b7d1) | Added the Sprint 2 research-paper discovery workflow. |

## Deployment Notes

### GitHub Pages

The static portfolio is served from `docs/`:

<https://amaniaslim.github.io/research-paper-discovery-agent/>

### Streamlit Community Cloud

Live application:

<https://research-paper-discovery-agent-bysmydwzhs4nepreseaurt.streamlit.app/>

Use the following deployment settings:

- Repository: `Amaniaslim/research-paper-discovery-agent`
- Branch: `main`
- Main file: `app.py`
- Python version: `3.12`

Optional variables from `.env.example` can be entered as Streamlit secrets.
Never commit `.streamlit/secrets.toml`.

## Security and Data Handling

- `.env`, credentials, private keys, uploaded PDFs, local databases, exports,
  caches, and generated archives are excluded from Git.
- The release ZIP is assembled from an allowlist by
  `scripts/create_final_zip.py`.
- The only public PDF intentionally included in a release is the Demo Day
  presentation under `docs/assets/`.
- Answers should always be verified against the displayed original sources.

## Limitations

- Ranking is transparent and rule-based rather than learned.
- Local summaries use titles and abstracts.
- The local embedding favors offline resilience over state-of-the-art semantic
  retrieval quality.
- OCR quality depends on the configured backend and the source document.
- Large PDFs require more processing time and storage.
- Grounded generation can be incomplete when relevant information is not
  retrieved.
- The application supports literature exploration; it does not replace reading,
  evaluating, and citing the original publications.

See [docs/limitations.md](docs/limitations.md) for additional operational
details.

## License

Released under the [MIT License](LICENSE).
