# Sprint 3 Description

Sprint 3 adds a PDF-RAG prototype on top of the Sprint 2 discovery workflow.

## Goal

Move from abstract-based overview to PDF-based question answering with visible
sources.

## Implemented Scope

- PDF upload
- Page-wise PDF text extraction with optional OCR fallback
- OCR backend selection: local Tesseract or a Baidu Unlimited-OCR compatible server
- Text chunking with page, section, and extraction metadata
- Chunk storage in ChromaDB with JSON fallback
- Retrieval of relevant chunks for a question, including section filters
- Optional SAIA answer generation
- Local fallback answer from retrieved chunks
- Source display with PDF name, page number, chunk ID, section, and extraction method
- Markdown export for the PDF-RAG answer and its traceable sources

## Demo Value

Sprint 3 demonstrates that the agent can answer questions from uploaded PDF full
texts and show where the answer came from.

## Target Users

The main users are students, researchers, and analysts who need to inspect long
papers quickly and still need answers that can be verified in the original PDF.

## Live Demo Script

1. Start with the problem: reading long papers is slow, and generic summaries
   are hard to verify.
2. Upload a full-text PDF from the ranked paper list.
3. Build the index and point out page-aware chunks, section metadata, and OCR
   fallback for scanned pages.
4. Ask the core-claims preset question to show paper-level synthesis.
5. Open the sources and show PDF name, page number, chunk ID, section, and
   extraction method.
6. Export the Markdown result as the handoff artifact.

## Feedback Addressed

- The workflow now shows a complete path from upload to Markdown export.
- OCR is available for scanned pages through local Tesseract or, following the
  professor recommendation, through a separately deployed Baidu Unlimited-OCR
  compatible endpoint.
- Retrieval quality is improved with lexical embeddings, reranking, and section
  filters.
- The demo can show both detail lookup and synthesis of core paper claims.
