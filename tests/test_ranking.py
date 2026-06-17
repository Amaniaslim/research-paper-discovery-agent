from __future__ import annotations

import paper_research_agent as pipeline


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
