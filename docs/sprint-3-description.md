# Sprint 3 Description

Sprint 3 adds a PDF-RAG prototype on top of the Sprint 2 discovery workflow.

## Goal

Move from abstract-based overview to PDF-based question answering with visible
sources.

## Implemented Scope

- PDF upload
- Page-wise PDF text extraction
- Text chunking with page metadata
- Chunk storage in ChromaDB with JSON fallback
- Retrieval of relevant chunks for a question
- Optional SAIA answer generation
- Local fallback answer from retrieved chunks
- Source display with PDF name, page number, and chunk ID
- Markdown export for the PDF-RAG answer

## Demo Value

Sprint 3 demonstrates that the agent can answer questions from uploaded PDF full
texts and show where the answer came from.
