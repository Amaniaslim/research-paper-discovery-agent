from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import paper_research_agent as pipeline  # noqa: E402
import rag_store  # noqa: E402


def main() -> None:
    review = pipeline.build_review(
        "security risks of agentic AI systems",
        limit=3,
        live=False,
    )
    markdown = pipeline.to_markdown(review)

    assert review.papers, "Expected ranked papers."
    assert "Literature Review" in markdown
    assert "Paper-Liste" in markdown
    assert rag_store.storage_backend() in {"ChromaDB", "JSON fallback"}

    print("Smoke check passed: discovery, Markdown export, and RAG store are available.")


if __name__ == "__main__":
    main()
