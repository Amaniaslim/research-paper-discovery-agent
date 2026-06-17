from __future__ import annotations

import rag_answer
import rag_retriever


def test_rag_question_prioritizes_vector_database_controls(monkeypatch) -> None:
    entries = [
        {
            "id": "general",
            "document": "General security controls include monitoring, logging, and governance.",
            "metadata": {"pdf_name": "paper.pdf", "page_number": 1, "chunk_id": "p1-c1"},
        },
        {
            "id": "rag",
            "document": (
                "RAG systems need access controls for vector databases, post-retrieval filtering, "
                "content verification before embedding, and rate-limiting."
            ),
            "metadata": {"pdf_name": "paper.pdf", "page_number": 4, "chunk_id": "p4-c1"},
        },
    ]
    monkeypatch.setattr(rag_retriever.rag_store, "query_chunks", lambda question, top_k=5: [])
    monkeypatch.setattr(rag_retriever.rag_store, "load_all_chunks", lambda: entries)

    results = rag_retriever.search_relevant_chunks("Which RAG vector database controls are discussed?", top_k=2)

    assert results[0]["chunk_id"] == "p4-c1"


def test_rag_fallback_answer_names_specific_controls(monkeypatch) -> None:
    monkeypatch.setenv("SAIA_API_KEY", "")
    chunks = [
        {
            "pdf_name": "paper.pdf",
            "page_number": 4,
            "chunk_id": "p4-c1",
            "text": (
                "RAG systems need access controls for vector databases, post-retrieval filtering, "
                "content verification before embedding, and rate-limiting."
            ),
        }
    ]

    result = rag_answer.generate_answer("Which RAG controls are relevant for vector databases?", chunks)

    assert "Access Controls für Vector Databases" in result["answer"]
    assert "Post-Retrieval Filtering" in result["answer"]
    assert "Content Verification vor Embedding" in result["answer"]
    assert "Rate-Limiting" in result["answer"]
