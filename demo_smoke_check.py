from __future__ import annotations

import paper_research_agent as pipeline
import rag_store


def main() -> None:
    review = pipeline.build_review(
        "security risks of agentic AI systems",
        limit=3,
        live=False,
    )
    markdown = pipeline.to_markdown(review)

    assert review.papers, "Expected ranked papers."
    assert "Sprint 2 Literature Review" in markdown
    assert "Paper-Liste" in markdown
    assert rag_store.storage_backend() in {"ChromaDB", "JSON fallback"}

    print("Smoke check passed: discovery, Markdown export, and RAG store are available.")


if __name__ == "__main__":
    main()
