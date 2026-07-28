from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_DIR / "papers.json"
DEFAULT_OUTPUT_PATH = PROJECT_DIR / "demo_output" / "review.md"
DEFAULT_QUERY = "security risks of agentic AI systems"


@dataclass
class Paper:
    id: str
    title: str
    abstract: str
    authors: list[str]
    year: int
    source: str
    url: str
    citations: int = 0
    relevance_score: float = 0.0


@dataclass
class PaperSummary:
    paper_id: str
    contribution: str
    methods: list[str]
    key_findings: list[str]
    limitations: list[str]
    keywords: list[str]
    summary_source: str = "heuristic-abstract"


@dataclass
class LiteratureReview:
    query: str
    papers: list[Paper]
    summaries: list[PaperSummary]
    clusters: dict[str, list[Paper]] = field(default_factory=dict)


DEMO_PAPERS = [
    Paper(
        id="arora-2025-agentic-security",
        title="Securing Agentic AI Systems -- A Multilayer Security Framework",
        authors=["Sunil Arora", "John Hastings"],
        year=2025,
        source="arXiv",
        citations=0,
        url="http://arxiv.org/abs/2512.18043v1",
        abstract=(
            "Securing Agentic Artificial Intelligence systems requires addressing "
            "complex cyber risks introduced by autonomous, decision-making, and "
            "adaptive behaviors. Existing AI security frameworks do not adequately "
            "address these challenges or the unique nuances of agentic AI. This "
            "research develops a lifecycle-aware security framework specifically "
            "designed for agentic AI systems using Design Science Research. The "
            "paper introduces MAAIS and the agentic AI CIAA concept."
        ),
    ),
    Paper(
        id="maiti-2026-zero-trust-agents",
        title="Caging the Agents: A Zero Trust Security Architecture for Autonomous AI in Healthcare",
        authors=["Saikat Maiti"],
        year=2026,
        source="arXiv",
        citations=0,
        url="http://arxiv.org/abs/2603.17419v1",
        abstract=(
            "Autonomous AI agents powered by large language models are being "
            "deployed in production with shell execution, file system access, "
            "database queries, and multi-party communication. The paper develops "
            "a six-domain threat model for agentic AI in healthcare covering "
            "credential exposure, execution capability abuse, network egress "
            "exfiltration, prompt integrity failures, database access risks, "
            "and fleet configuration drift."
        ),
    ),
    Paper(
        id="engelberg-2026-ispm",
        title="Sola-Visibility-ISPM: Benchmarking Agentic AI for Identity Security Posture Management Visibility",
        authors=["Gal Engelberg", "Konstantin Koutsyi", "Leon Goldberg", "Reuven Elezra"],
        year=2026,
        source="arXiv",
        citations=0,
        url="http://arxiv.org/abs/2601.07880v1",
        abstract=(
            "Identity Security Posture Management is a core challenge for modern "
            "enterprises operating across cloud and SaaS environments. This work "
            "provides a practical and reproducible benchmark for evaluating "
            "agentic AI systems in identity security and establishes a foundation "
            "for future ISPM benchmarks covering advanced identity analysis and "
            "governance tasks."
        ),
    ),
    Paper(
        id="zhang-2026-regulatory-agentic-ai",
        title="Security, privacy, and agentic AI in a regulatory view: From definitions and distinctions to provisions and reflections",
        authors=["Shiliang Zhang", "Sabita Maharjan"],
        year=2026,
        source="arXiv",
        citations=0,
        url="http://arxiv.org/abs/2603.18914v1",
        abstract=(
            "The rapid proliferation of artificial intelligence technologies has "
            "led to a dynamic regulatory landscape. As AI paradigms shift towards "
            "greater autonomy in the form of agentic AI, it becomes increasingly "
            "challenging to articulate regulatory stipulations. This challenge is "
            "acute in security and privacy, where autonomous agents blur legal "
            "and technical boundaries."
        ),
    ),
    Paper(
        id="zou-2021-syzscope",
        title="SyzScope: Revealing High-Risk Security Impacts of Fuzzer-Exposed Bugs in Linux kernel",
        authors=["Xiaochen Zou", "Guoren Li", "Weiteng Chen", "Hang Zhang"],
        year=2021,
        source="arXiv",
        citations=0,
        url="http://arxiv.org/abs/2111.06002v1",
        abstract=(
            "Fuzzing is an effective bug finding approach for software. The lack "
            "of understanding of security impact can lead to delayed bug fixes "
            "and patch propagation. SyzScope helps reveal high-risk security "
            "impacts of fuzzer-exposed bugs in the Linux kernel."
        ),
    ),
]


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "are",
    "into",
    "using",
    "systems",
    "artificial",
    "intelligence",
}


def load_demo_papers(data_path: Path = DEFAULT_DATA_PATH) -> list[Paper]:
    """Load optional local paper JSON, otherwise use embedded demo papers."""
    if not data_path.exists():
        return [Paper(**paper.__dict__) for paper in DEMO_PAPERS]

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return [Paper(**paper) for paper in payload["papers"]]


def build_review(
    query: str,
    limit: int = 5,
    data_path: Path = DEFAULT_DATA_PATH,
) -> LiteratureReview:
    """Rank, summarize, and synthesize saved paper records."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Please enter a research question.")

    ranked_papers = rank_papers(clean_query, load_demo_papers(data_path))[:limit]
    summaries = summarize_papers(ranked_papers)
    clusters = cluster_papers(ranked_papers)
    return LiteratureReview(clean_query, ranked_papers, summaries, clusters)


def rank_papers(query: str, papers: list[Paper]) -> list[Paper]:
    query_terms = set(_keywords(query))
    ranked = []
    for paper in papers:
        paper_terms = set(_keywords(f"{paper.title} {paper.abstract}"))
        overlap = len(query_terms & paper_terms) / max(len(query_terms), 1)
        recency = max(paper.year - 2020, 0) / 10
        paper.relevance_score = round((overlap * 0.75) + (recency * 0.25), 4)
        ranked.append(paper)
    return sorted(ranked, key=lambda paper: paper.relevance_score, reverse=True)


def summarize_papers(papers: list[Paper]) -> list[PaperSummary]:
    return [_summarize_paper(paper) for paper in papers]


def cluster_papers(papers: list[Paper]) -> dict[str, list[Paper]]:
    clusters: dict[str, list[Paper]] = {}
    for paper in papers:
        keyword = _keywords(paper.title)[0].title()
        clusters.setdefault(keyword, []).append(paper)
    return clusters


def export_review(review: LiteratureReview, output_path: Path = DEFAULT_OUTPUT_PATH) -> str:
    markdown = to_markdown(review)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def to_markdown(review: LiteratureReview) -> str:
    lines = [
        f"# Literature Review: {review.query}",
        "",
        "This review is based on saved paper metadata and abstracts.",
        "",
        "## Executive Summary",
        "",
        f"- Papers reviewed: {len(review.papers)}",
        f"- Topic clusters: {len(review.clusters)}",
        "- Summaries source: heuristic extraction from abstracts",
        "",
        "## Topic Clusters",
        "",
    ]

    for cluster, papers in review.clusters.items():
        lines.append(f"### {cluster}")
        lines.extend(f"- {paper.title}" for paper in papers)
        lines.append("")

    summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
    lines.extend(["## Annotated Papers", ""])
    for paper in review.papers:
        summary = summaries_by_id[paper.id]
        lines.extend(
            [
                f"### {paper.title}",
                "",
                f"- Source: {paper.source}",
                f"- Authors: {', '.join(paper.authors)}",
                f"- Year: {paper.year}",
                f"- Citations: {paper.citations}",
                f"- Relevance score: {paper.relevance_score}",
                f"- URL: {paper.url}",
                f"- Summary source: {summary.summary_source}",
                "",
                f"**Contribution:** {summary.contribution}",
                "",
                "**Methods:**",
            ]
        )
        lines.extend(f"- {method}" for method in summary.methods)
        lines.extend(["", "**Key Findings:**"])
        lines.extend(f"- {finding}" for finding in summary.key_findings)
        lines.extend(["", "**Limitations:**"])
        lines.extend(f"- {limitation}" for limitation in summary.limitations)
        lines.extend(["", f"**Keywords:** {', '.join(summary.keywords)}", ""])

    return "\n".join(lines)


def _summarize_paper(paper: Paper) -> PaperSummary:
    sentences = _sentences(paper.abstract)
    keywords = _keywords(f"{paper.title} {paper.abstract}")[:8]
    limitations = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in ["lack", "challenge", "risk", "limitation"])
    ]
    return PaperSummary(
        paper_id=paper.id,
        contribution=sentences[0] if sentences else paper.abstract,
        methods=sentences[1:3] or sentences[:1],
        key_findings=sentences[3:5] or sentences[:1],
        limitations=limitations[:2] or ["Not explicit in abstract."],
        keywords=keywords,
    )


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.lower())
    result = []
    for word in words:
        if word not in STOPWORDS and word not in result:
            result.append(word)
    return result


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an offline literature review.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--limit", type=int, default=5, choices=range(1, 6))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    review = build_review(args.query, limit=args.limit)
    export_review(review, args.output)

    print(f"Offline literature review generated: {args.output.resolve()}")
    print(f"Papers ranked and summarized: {len(review.papers)}")
    for position, paper in enumerate(review.papers, start=1):
        print(f"{position}. {paper.relevance_score:.4f} - {paper.title}")


if __name__ == "__main__":
    main()
