from __future__ import annotations

import paper_research_agent as pipeline
import rag_answer


def test_markdown_export(tmp_path) -> None:
    review = pipeline.build_review(
        "security risks of agentic AI systems",
        limit=2,
        live=False,
    )

    markdown = pipeline.export_review(review, tmp_path / "review.md")

    assert "Sprint 2 Literature Review" in markdown
    assert "security risks of agentic AI systems" in markdown
    assert (tmp_path / "review.md").exists()


def test_answer_fallback_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("SAIA_API_KEY", "")
    chunks = [
        {
            "pdf_name": "paper.pdf",
            "page_number": 2,
            "chunk_id": "p2-c1",
            "text": "The document discusses prompt injection and tool misuse risks.",
        }
    ]

    result = rag_answer.generate_answer("Which risks are discussed?", chunks)

    assert result["mode"] == "fallback"
    assert "Auf Basis der gefundenen PDF-Quellen" in result["answer"]
    assert "[paper.pdf, page 2]" in result["answer"]
    assert "Vollstaendigkeit" in result["answer"]
