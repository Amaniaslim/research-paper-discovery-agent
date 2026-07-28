from __future__ import annotations

import rag_answer
import rag_retriever
import rag_store


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


def test_retrieval_can_filter_by_section(monkeypatch) -> None:
    entries = [
        {
            "id": "abstract",
            "document": "The paper introduces an agentic AI security framework.",
            "metadata": {
                "pdf_name": "paper.pdf",
                "page_number": 1,
                "chunk_id": "p1-c1",
                "section": "Abstract",
            },
        },
        {
            "id": "limitations",
            "document": "The limitations include deployment risk and incomplete evaluation.",
            "metadata": {
                "pdf_name": "paper.pdf",
                "page_number": 9,
                "chunk_id": "p9-c1",
                "section": "Limitations",
            },
        },
    ]
    monkeypatch.setattr(rag_retriever.rag_store, "query_chunks", lambda question, top_k=5: [])
    monkeypatch.setattr(rag_retriever.rag_store, "load_all_chunks", lambda: entries)

    results = rag_retriever.search_relevant_chunks("What limitations are discussed?", top_k=3, sections=["Limitations"])

    assert [result["chunk_id"] for result in results] == ["p9-c1"]
    assert results[0]["section"] == "Limitations"


def test_local_embedding_rewards_term_overlap() -> None:
    question = rag_store.local_embedding("vector database access controls for RAG retrieval")
    relevant = rag_store.local_embedding("RAG systems need access controls for vector databases")
    unrelated = rag_store.local_embedding("qualitative interviews about classroom collaboration")

    assert _dot(question, relevant) > _dot(question, unrelated)


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


def test_retrieval_adds_neighboring_chunks(monkeypatch) -> None:
    entries = [
        {
            "id": f"chunk-{number}",
            "document": f"Context number {number} about retrieval controls.",
            "metadata": {
                "pdf_name": "paper.pdf",
                "page_number": 4,
                "chunk_id": f"p4-c{number}",
                "section": "Methods",
            },
        }
        for number in range(1, 4)
    ]
    monkeypatch.setattr(
        rag_retriever.rag_store,
        "query_chunks",
        lambda question, top_k=5: [entries[1]],
    )
    monkeypatch.setattr(rag_retriever.rag_store, "load_all_chunks", lambda: entries)

    results = rag_retriever.search_relevant_chunks(
        "Which retrieval controls are discussed?",
        top_k=1,
        neighbor_radius=1,
    )

    assert [result["chunk_id"] for result in results] == ["p4-c1", "p4-c2", "p4-c3"]
    assert results[0]["is_context"] is True
    assert results[2]["is_context"] is True


def _dot(left: list[float], right: list[float]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right))
