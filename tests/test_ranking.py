from __future__ import annotations

import paper_research_agent as pipeline
from review_core import Paper


def test_offline_ranking_returns_relevant_papers() -> None:
    review = pipeline.build_review(
        "security risks of agentic AI systems",
        limit=3,
        live=False,
    )

    assert len(review.papers) == 3
    assert review.papers[0].relevance_score >= review.papers[-1].relevance_score
    top_text = f"{review.papers[0].title} {review.papers[0].abstract}".lower()
    assert "agent" in top_text or "security" in top_text


def test_live_disabled_uses_fallback_status() -> None:
    pipeline.build_review("security risks of agentic AI systems", limit=2, live=False)

    assert pipeline.LAST_RETRIEVAL_STATUS["mode"] in {"cache", "fallback"}


def test_normalization_removes_duplicate_papers() -> None:
    papers = [
        Paper(
            id="one",
            title="  Secure Agentic Systems  ",
            abstract="A first abstract.",
            authors=["A. Researcher"],
            year=2025,
            source="arXiv live",
            url="https://arxiv.org/abs/1234.5678",
        ),
        Paper(
            id="two",
            title="Secure Agentic Systems",
            abstract="A duplicate record.",
            authors=["A. Researcher"],
            year=2025,
            source="Semantic Scholar live",
            url="https://arxiv.org/abs/1234.5678",
        ),
    ]

    normalized = pipeline.normalize_papers(papers)

    assert len(normalized) == 1
    assert normalized[0].title == "Secure Agentic Systems"
