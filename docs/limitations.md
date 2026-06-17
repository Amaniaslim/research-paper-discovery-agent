# Limitations

This project is a sprint-based educational prototype.

## Current limitations

- PDF-RAG works best with text-based PDFs.
- Scanned PDFs are not supported yet because OCR is not implemented.
- Ranking is rule-based and transparent, but not ML-based yet.
- ChromaDB is used for memory and retrieval.
- The current local embedding is simple and deterministic for demo stability.
- Real semantic embeddings are planned as a future improvement.
- LLM answer generation is optional and depends on API configuration.
- The agent supports the first research overview but does not replace reading and
  evaluating scientific papers.

## Future improvements

- OCR support for scanned PDFs.
- Better semantic embeddings for retrieval.
- Stronger evaluation of ranking and retrieval quality.
- More complete citation parsing and bibliography export.
- Refactoring core modules into a package structure.
