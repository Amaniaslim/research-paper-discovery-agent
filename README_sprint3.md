# Sprint 3 - PDF-RAG Research Agent

Sprint 3 extends the Research Paper Discovery Agent from abstract-based discovery
to PDF-RAG. The agent can now upload PDFs, extract page-wise text, split text into
chunks, store chunks in ChromaDB, retrieve relevant chunks for a question, and
generate a source-grounded answer with SAIA.

## Goal

The goal is to answer questions from uploaded PDF documents instead of relying
only on metadata and abstracts. Answers must be grounded in retrieved PDF chunks
and include source references with PDF name and page number.

## Install Dependencies

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sprint 3 adds:

- `pymupdf` for PDF text extraction
- `chromadb` for persistent chunk storage
- optional `pytesseract` and `Pillow` for OCR on scanned pages
- `python-dotenv` for `.env` API configuration
- `streamlit` for the UI
- `pytest` for lightweight project tests

## Run The App

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app_sprint3.py
```

Or, if the virtual environment is active:

```powershell
streamlit run app_sprint3.py
```

## Smoke Check

```powershell
.\.venv\Scripts\python.exe .\demo_smoke_check.py
```

The smoke check verifies the offline discovery workflow, Markdown export, and
active RAG storage backend.

## PDF Upload

PDFs are uploaded in the `PDF-RAG Demo` tab. Uploaded files are saved to:

```text
data/pdfs/
```

The UI shows the PDF file name, file size, and upload/indexing status.

## PDF Text Extraction

`pdf_loader.py` uses PyMuPDF (`fitz`) to extract text page by page. Each extracted
page keeps structured metadata:

- `pdf_name`
- `page_number`
- `section`
- `extraction_method`
- `text`

If OCR is enabled in the UI, pages with little or no selectable text are rendered
and passed to the selected OCR backend. The lightweight backend is local
Tesseract. The advanced backend follows the professor feedback and can call a
separately started Baidu Unlimited-OCR server through an OpenAI-compatible
endpoint.

Optional Unlimited-OCR configuration in `.env`:

```env
UNLIMITED_OCR_BASE_URL=http://127.0.0.1:10000
UNLIMITED_OCR_MODEL=Unlimited-OCR
UNLIMITED_OCR_API_KEY=
```

Unlimited-OCR is not started by this app because it is a large GPU-oriented
model. The app only provides the integration point.

## Chunking

`chunking.py` splits extracted page text into overlapping chunks. The default
chunk size is around 1000 characters with 150 characters overlap. Each chunk
keeps:

- `pdf_name`
- `page_number`
- `chunk_id`
- `section`
- `extraction_method`
- `text`

## ChromaDB Chunk Store

`rag_store.py` stores chunks in a persistent ChromaDB collection named:

```text
paper_chunks
```

The ChromaDB path is:

```text
demo_output/pdf_chroma/
```

Each chunk is stored with:

- document text
- metadata: `pdf_name`, `page_number`, `chunk_id`, `section`, `extraction_method`
- stable ID based on `pdf_name + page_number + chunk_id`

If ChromaDB is unavailable, the app stores chunks in:

```text
demo_output/pdf_chunks_cache.json
```

## Retrieval

`rag_retriever.py` retrieves the most relevant chunks for a user question.
Retrieval now combines ChromaDB with a deterministic lexical embedding, keyword
reranking, RAG-specific phrase boosts, and optional section filters from the UI.
The UI shows source information for each retrieved chunk:

- PDF name
- page number
- chunk ID
- section
- extraction method

## SAIA LLM Answer Generation

`rag_answer.py` uses the existing `.env` configuration:

```env
SAIA_MODEL=mistral-large-3-675b-instruct-2512
SAIA_API_KEY=...
SAIA_BASE_URL=https://chat-ai.academiccloud.de/v1
ENABLE_LLM_SUMMARIES=true
```

The answer prompt instructs the model:

```text
Answer only based on the provided sources. If the answer is not in the sources,
say that the documents do not contain enough information.
```

The answer should include source references like:

```text
[paper.pdf, page 3]
```

## Fallback Behavior

The app is designed to keep working even if external services are unavailable:

- If ChromaDB is unavailable, chunks are stored in JSON.
- If SAIA is unavailable or no API key is configured, the answer falls back to a
  local list of the most relevant chunks.
- If no chunks are found, the app says that the documents do not contain enough
  information.

## Demo Workflow

The Streamlit demo uses four main tabs:

1. `Überblick`
2. `Paper-Suche`
3. `PDF-RAG Demo`
4. `Export & Memory`

The `PDF-RAG Demo` tab contains the PDF workflow in one guided flow:

1. Upload the full-text PDF of a relevant paper.
2. Index the PDF into page-aware and section-aware chunks.
3. Ask either a detail question or the preset question about the paper's core claims.
4. Review answer sources with PDF name, page, chunk ID, section, and extraction method.
5. Export the result as Markdown.

This keeps the Sprint 1 and Sprint 2 functionality visible while Sprint 3 adds
PDF-RAG on top of it.

## Export

The `Export` tab writes and downloads:

```text
demo_output/sprint3_pdf_rag_answer.md
```

The Sprint 3 Markdown export contains:

- question
- answer
- answer mode
- selected sections
- retrieved sources with PDF name, page number, chunk ID, section, extraction method, and score where available

BibTeX and APA polish are future work.

## Sprint Review Feedback Addressed

- Full-PDF workflow is visible from upload to export.
- Source traceability keeps PDF name, page number, chunk ID, section, and extraction method.
- OCR support is available as an optional fallback for scanned pages, including
  a lightweight Tesseract path and an advanced Baidu Unlimited-OCR server path.
- Retrieval quality is improved with lexical embeddings, reranking, and section filters.
- The demo includes a core-claims question preset to show paper-level synthesis, not only sentence-level lookup.

## Target Audience

The strongest fit is for students, researchers, and analysts who need quick,
source-grounded orientation in long research papers before reading them deeply.

## Current Limitations

- OCR requires optional Python packages and either a local Tesseract binary or a
  separately deployed Unlimited-OCR service.
- Local embeddings are improved but still less powerful than a dedicated embedding API.
- The app does not yet parse citations or bibliography sections separately.
- Source grounding depends on retrieved chunks, not full-document reasoning.
