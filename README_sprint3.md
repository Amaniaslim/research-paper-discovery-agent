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
- `text`

## Chunking

`chunking.py` splits extracted page text into overlapping chunks. The default
chunk size is around 1000 characters with 150 characters overlap. Each chunk
keeps:

- `pdf_name`
- `page_number`
- `chunk_id`
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
- metadata: `pdf_name`, `page_number`, `chunk_id`
- stable ID based on `pdf_name + page_number + chunk_id`

If ChromaDB is unavailable, the app stores chunks in:

```text
demo_output/pdf_chunks_cache.json
```

## Retrieval

`rag_retriever.py` retrieves the top 3 to 5 relevant chunks for a user question.
The UI shows source information for each retrieved chunk:

- PDF name
- page number
- chunk ID

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
2. Index the PDF into page-aware chunks.
3. Ask a question against the indexed PDF text.
4. Review answer sources.

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
- retrieved sources with PDF name and page number

BibTeX, APA, and richer structured exports are future work.

## Current Limitations

- PDF extraction depends on selectable text; scanned PDFs without OCR may return
  little or no text.
- Chunk embeddings use a simple local deterministic embedding for stability.
- The app does not yet use a dedicated embedding API.
- The app does not yet parse citations or bibliography sections separately.
- Source grounding depends on retrieved chunks, not full-document reasoning.
