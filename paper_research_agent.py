from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import review_core as core

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


PROJECT_DIR = Path(__file__).resolve().parent
if load_dotenv is not None:
    load_dotenv(PROJECT_DIR / ".env")

DEFAULT_OUTPUT_PATH = PROJECT_DIR / "demo_output" / "literature_review.md"
DEFAULT_CACHE_PATH = PROJECT_DIR / "demo_output" / "paper_cache.json"
DEFAULT_QUERY = core.DEFAULT_QUERY
ARXIV_API_URLS = [
    "https://export.arxiv.org/api/query",
    "http://export.arxiv.org/api/query",
]
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
LAST_RETRIEVAL_STATUS = {
    "mode": "not-run",
    "query": "",
    "arxiv_query": "",
    "message": "",
    "summary_mode": "heuristic",
}
GERMAN_QUERY_TERMS = {
    "agentische": "agentic",
    "agentischen": "agentic",
    "ki": "AI",
    "kuenstliche intelligenz": "artificial intelligence",
    "sicherheit": "security",
    "sicherheitsrisiken": "security risks",
    "risiken": "risks",
    "datenschutz": "privacy",
    "autonome": "autonomous",
    "systeme": "systems",
    "systemen": "systems",
    "agenten": "agents",
}
SEARCH_STOPWORDS = core.STOPWORDS | {
    "what",
    "main",
    "which",
    "how",
    "why",
    "does",
    "are",
    "the",
    "of",
    "durch",
    "welche",
    "entstehen",
    "was",
    "wie",
    "aktuelle",
    "aktuellen",
    "papers",
    "paper",
    "beschaeftigen",
    "sich",
}
AGENT_TERMS = {
    "agentic",
    "agent",
    "agents",
    "autonomous",
    "autonomy",
    "llm",
    "llms",
    "language",
    "multi-agent",
}
SECURITY_TERMS = {
    "security",
    "secure",
    "risk",
    "risks",
    "threat",
    "threats",
    "attack",
    "attacks",
    "vulnerability",
    "vulnerabilities",
    "privacy",
    "safety",
    "governance",
    "prompt",
    "injection",
    "identity",
}
OFF_TOPIC_TERMS = {
    "antenna",
    "wireless",
    "sensor",
    "sensors",
    "liveness",
    "biometric",
    "neuromuscular",
    "vehicle",
    "mobility",
    "clinical",
    "patient",
}
MIN_FOCUSED_SCORE = 0.18


def build_review(
    query: str,
    limit: int = 8,
    live: bool = True,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> core.LiteratureReview:
    """Build a review with live retrieval and a stable offline fallback."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Please enter a research question.")

    search_query = expand_query(clean_query)
    papers = retrieve_papers(search_query, limit=max(limit * 2, 10), live=live, cache_path=cache_path)
    ranked_papers = select_ranked_papers(search_query, papers, limit)
    summaries = summarize_papers(clean_query, ranked_papers)
    clusters = core.cluster_papers(ranked_papers)
    return core.LiteratureReview(clean_query, ranked_papers, summaries, clusters)


def summarize_papers(query: str, papers: list[core.Paper]) -> list[core.PaperSummary]:
    """Summarize papers with SAIA when configured, otherwise use local heuristics."""
    heuristic_summaries = core.summarize_papers(papers)
    if not _saia_enabled():
        LAST_RETRIEVAL_STATUS["summary_mode"] = "heuristic"
        return heuristic_summaries

    summaries: list[core.PaperSummary] = []
    fallback_by_id = {summary.paper_id: summary for summary in heuristic_summaries}
    used_llm = False
    for paper in papers:
        fallback = fallback_by_id[paper.id]
        try:
            summaries.append(_summarize_paper_with_saia(query, paper, fallback))
            used_llm = True
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError):
            summaries.append(fallback)

    LAST_RETRIEVAL_STATUS["summary_mode"] = "saia" if used_llm else "heuristic"
    return summaries


def expand_query(query: str) -> str:
    """Add English search terms for common German research questions."""
    seen_terms = set(core._keywords(query))
    translated_terms: list[str] = []
    normalized = query.lower()
    for german, english in GERMAN_QUERY_TERMS.items():
        if german not in normalized:
            continue
        for term in core._keywords(english):
            if term not in seen_terms:
                translated_terms.append(term)
                seen_terms.add(term)
    return " ".join([query, *translated_terms])


def retrieve_papers(
    query: str,
    limit: int = 10,
    live: bool = True,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> list[core.Paper]:
    """Retrieve papers from arXiv when possible, otherwise use cache/demo papers."""
    LAST_RETRIEVAL_STATUS.update(
        {"mode": "starting", "query": query, "arxiv_query": build_arxiv_search_query(query), "message": ""}
    )
    if live:
        try:
            papers = fetch_arxiv_papers(query, limit=limit)
        except (OSError, urllib.error.URLError, ET.ParseError, TimeoutError) as exc:
            papers = []
            LAST_RETRIEVAL_STATUS.update(
                {
                    "mode": "fallback",
                    "message": f"Live-arXiv konnte nicht erreicht werden: {exc}",
                }
            )
        if papers:
            normalized = normalize_papers(papers)
            save_cache(normalized, query, cache_path)
            LAST_RETRIEVAL_STATUS.update(
                {
                    "mode": "live",
                    "message": f"{len(normalized)} Paper live von arXiv geladen.",
                }
            )
            return normalized
        try:
            papers = fetch_semantic_scholar_papers(query, limit=limit)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            existing_message = LAST_RETRIEVAL_STATUS.get("message", "")
            semantic_message = f"Semantic Scholar konnte nicht erreicht werden: {exc}"
            if existing_message:
                semantic_message = f"{existing_message} {semantic_message}"
            LAST_RETRIEVAL_STATUS.update(
                {
                    "mode": "fallback",
                    "message": semantic_message,
                }
            )
            papers = []
        if papers:
            normalized = normalize_papers(papers)
            save_cache(normalized, query, cache_path)
            LAST_RETRIEVAL_STATUS.update(
                {
                    "mode": "live",
                    "message": f"{len(normalized)} Paper live von Semantic Scholar geladen.",
                }
            )
            return normalized
        if not LAST_RETRIEVAL_STATUS["message"]:
            LAST_RETRIEVAL_STATUS.update(
                {
                    "mode": "fallback",
                    "message": "Live-APIs haben keine passenden Paper zurueckgegeben.",
                }
            )

    cached = load_cache(cache_path)
    if cached:
        cached = _mark_cached(cached)
        LAST_RETRIEVAL_STATUS.update(
            {
                "mode": "cache",
                "arxiv_query": f"Lokaler Cache fuer: {query}",
                "message": f"{len(cached)} Paper aus dem lokalen arXiv-Cache geladen.",
            }
        )
        return normalize_papers(cached)

    existing_message = LAST_RETRIEVAL_STATUS.get("message", "")
    if existing_message:
        message = f"{existing_message} Kein Cache vorhanden; Demodaten werden genutzt."
    elif live:
        message = "Kein Live-Ergebnis und kein Cache vorhanden; Demodaten werden genutzt."
    else:
        message = "Live-arXiv ist ausgeschaltet und kein Cache vorhanden; Demodaten werden genutzt."
    LAST_RETRIEVAL_STATUS.update({"mode": "fallback", "message": message})
    return core.load_demo_papers()


def fetch_arxiv_papers(query: str, limit: int = 10) -> list[core.Paper]:
    last_error: Exception | None = None
    collected: list[core.Paper] = []
    for search_query in build_arxiv_search_queries(query):
        LAST_RETRIEVAL_STATUS["arxiv_query"] = search_query
        try:
            papers = _fetch_arxiv_query(search_query, limit)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                LAST_RETRIEVAL_STATUS.update(
                    {
                        "mode": "fallback",
                        "message": (
                            "arXiv Rate Limit erreicht: zu viele Anfragen in kurzer Zeit. "
                            "Bitte kurz warten; bis dahin werden Fallback-Daten genutzt."
                        ),
                    }
                )
                return []
            last_error = exc
            continue
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            continue
        if papers:
            collected.extend(papers)
            if len(normalize_papers(collected)) >= limit:
                return normalize_papers(collected)
        time.sleep(1)

    if collected:
        return normalize_papers(collected)
    if last_error is not None:
        raise last_error
    return []


def _saia_enabled() -> bool:
    key = os.getenv("SAIA_API_KEY", "").strip()
    if not key or key.startswith("REPLACE_WITH"):
        return False
    return os.getenv("ENABLE_LLM_SUMMARIES", "true").strip().lower() in {"1", "true", "yes", "on"}


def _summarize_paper_with_saia(
    query: str,
    paper: core.Paper,
    fallback: core.PaperSummary,
) -> core.PaperSummary:
    prompt = (
        "Summarize this research paper for a literature discovery agent. "
        "Return only valid JSON with these keys: contribution, methods, key_findings, "
        "limitations, keywords. The list fields must be arrays of short strings.\n\n"
        f"Research question: {query}\n"
        f"Title: {paper.title}\n"
        f"Year: {paper.year}\n"
        f"Source: {paper.source}\n"
        f"Abstract: {_truncate(paper.abstract, 2200)}"
    )
    data = _call_saia_chat(prompt)
    return core.PaperSummary(
        paper_id=paper.id,
        contribution=str(data.get("contribution") or fallback.contribution),
        methods=_string_list(data.get("methods")) or fallback.methods,
        key_findings=_string_list(data.get("key_findings")) or fallback.key_findings,
        limitations=_string_list(data.get("limitations")) or fallback.limitations,
        keywords=_string_list(data.get("keywords")) or fallback.keywords,
        summary_source=f"saia:{os.getenv('SAIA_MODEL', '').strip()}",
    )


def _call_saia_chat(prompt: str) -> dict:
    api_key = os.getenv("SAIA_API_KEY", "").strip()
    base_url = os.getenv("SAIA_BASE_URL", "https://chat-ai.academiccloud.de/v1").strip().rstrip("/")
    model = os.getenv("SAIA_MODEL", "mistral-large-3-675b-instruct-2512").strip()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise scientific paper summaries. "
                    "You always answer with valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 450,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ResearchPaperDiscoveryAgent/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        response_payload = json.loads(response.read().decode("utf-8"))

    content = response_payload["choices"][0]["message"]["content"]
    return _parse_json_object(content)


def _parse_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def fetch_semantic_scholar_papers(query: str, limit: int = 10) -> list[core.Paper]:
    LAST_RETRIEVAL_STATUS["arxiv_query"] = f"Semantic Scholar: {query}"
    params = urllib.parse.urlencode(
        {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,authors,year,url,citationCount",
        }
    )
    headers = {"User-Agent": "ResearchPaperDiscoveryAgent/1.0"}
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key

    request = urllib.request.Request(
        f"{SEMANTIC_SCHOLAR_API_URL}?{params}",
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    papers: list[core.Paper] = []
    for item in payload.get("data", []):
        title = _clean_text(item.get("title") or "")
        abstract = _clean_text(item.get("abstract") or "")
        if not title or not abstract:
            continue
        authors = [
            _clean_text(author.get("name") or "")
            for author in item.get("authors", [])
            if author.get("name")
        ]
        url = item.get("url") or ""
        papers.append(
            core.Paper(
                id=_paper_id(url, title),
                title=title,
                abstract=abstract,
                authors=authors,
                year=item.get("year") or 0,
                source="Semantic Scholar live",
                url=url,
                citations=item.get("citationCount") or 0,
            )
        )
    return papers


def build_arxiv_search_query(query: str) -> str:
    """Return the first arXiv query used for diagnostics."""
    return build_arxiv_search_queries(query)[0]


def build_arxiv_search_queries(query: str) -> list[str]:
    """Convert a natural-language question into strict and broad arXiv queries."""
    keywords = [
        keyword
        for keyword in core._keywords(query)
        if keyword not in SEARCH_STOPWORDS
    ]
    preferred = [
        keyword
        for keyword in keywords
        if keyword
        in {
            "agentic",
            "agents",
            "security",
            "risks",
            "privacy",
            "autonomous",
            "prompt",
            "injection",
            "identity",
            "governance",
        }
    ]
    terms = preferred[:6] or keywords[:6] or ["agentic", "security"]
    queries: list[str] = []
    if any(term in terms for term in AGENT_TERMS) and any(term in terms for term in SECURITY_TERMS):
        queries.extend(
            [
                "all:agentic AND all:security",
                "all:agentic AND all:risk",
                "all:agentic AND all:privacy",
                "all:agents AND all:security",
                "all:autonomous AND all:security",
                "all:llm AND all:security",
            ]
        )

    strict_terms = [term for term in terms if term not in {"risks"}][:3] or terms[:3]
    queries.append(" AND ".join(f"all:{term}" for term in strict_terms))
    if len(terms) >= 3:
        queries.append(" AND ".join(f"all:{term}" for term in terms[:2]))

    broad_terms = [
        term
        for term in terms[:5]
        if term not in {"security", "risks", "risk"}
    ]
    if len(broad_terms) >= 2:
        queries.append(" AND ".join(f"all:{term}" for term in broad_terms[:2]))
    return list(dict.fromkeys(query for query in queries if query))


def _fetch_arxiv_query(search_query: str, limit: int) -> list[core.Paper]:
    params = urllib.parse.urlencode(
        {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    payload = b""
    last_error: Exception | None = None
    for api_url in ARXIV_API_URLS:
        request = urllib.request.Request(
            f"{api_url}?{params}",
            headers={"User-Agent": "ResearchPaperDiscoveryAgent/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            raise exc
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
    if not payload and last_error is not None:
        raise last_error

    root = ET.fromstring(payload)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: list[core.Paper] = []
    for entry in root.findall("atom:entry", ns):
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        url = entry.findtext("atom:id", default="", namespaces=ns).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns)
        year = _year_from_date(published)
        authors = [
            _clean_text(author.findtext("atom:name", default="", namespaces=ns))
            for author in entry.findall("atom:author", ns)
        ]
        if not title or not abstract:
            continue
        papers.append(
            core.Paper(
                id=_paper_id(url, title),
                title=title,
                abstract=abstract,
                authors=[author for author in authors if author],
                year=year,
                source="arXiv live",
                url=url,
            )
        )
    return papers


def normalize_papers(papers: list[core.Paper]) -> list[core.Paper]:
    """Deduplicate and normalize records before ranking."""
    seen: set[str] = set()
    normalized: list[core.Paper] = []
    for paper in papers:
        title = _clean_text(paper.title or "")
        abstract = _clean_text(paper.abstract or "")
        url = _clean_text(paper.url or "")
        key = _paper_id(url, title)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            core.Paper(
                id=key,
                title=title or "Kein Titel verfuegbar",
                abstract=abstract or "Kein Abstract verfuegbar.",
                authors=[_clean_text(author) for author in (paper.authors or []) if _clean_text(author)],
                year=paper.year if isinstance(paper.year, int) else 0,
                source=_clean_text(paper.source or "") or "Keine Quelle verfuegbar",
                url=url,
                citations=paper.citations if isinstance(paper.citations, int) else 0,
                relevance_score=paper.relevance_score,
            )
        )
    return normalized


def rank_papers(query: str, papers: list[core.Paper]) -> list[core.Paper]:
    query_terms = {term for term in core._keywords(query) if term not in SEARCH_STOPWORDS}
    security_focused = bool(query_terms & SECURITY_TERMS)
    agent_focused = bool(query_terms & AGENT_TERMS)
    ranked: list[core.Paper] = []
    for paper in papers:
        title_terms = set(core._keywords(paper.title))
        abstract_terms = set(core._keywords(paper.abstract))
        paper_terms = title_terms | abstract_terms
        overlap_count = len(query_terms & paper_terms)
        has_security_signal = bool(paper_terms & SECURITY_TERMS)
        has_agent_signal = bool(paper_terms & AGENT_TERMS)
        if security_focused and not has_security_signal:
            continue
        if agent_focused and not has_agent_signal:
            continue
        if overlap_count == 0:
            continue
        if security_focused and agent_focused and _looks_off_topic(title_terms, abstract_terms):
            continue

        title_overlap = len(query_terms & title_terms) / max(len(query_terms), 1)
        abstract_overlap = len(query_terms & abstract_terms) / max(len(query_terms), 1)
        coverage = overlap_count / max(len(query_terms), 1)
        recency = min(max(paper.year - 2020, 0) / 10, 0.6)
        paper.relevance_score = round(
            (title_overlap * 0.35)
            + (abstract_overlap * 0.30)
            + (coverage * 0.20)
            + (recency * 0.15),
            4,
        )
        ranked.append(paper)
    return sorted(ranked, key=lambda paper: paper.relevance_score, reverse=True)


def _looks_off_topic(title_terms: set[str], abstract_terms: set[str]) -> bool:
    title_has_core_signal = bool(title_terms & (AGENT_TERMS | SECURITY_TERMS))
    off_topic_hits = title_terms & OFF_TOPIC_TERMS
    if title_has_core_signal:
        return False
    return len(off_topic_hits) >= 1 or len(abstract_terms & OFF_TOPIC_TERMS) >= 2


def select_ranked_papers(query: str, papers: list[core.Paper], limit: int) -> list[core.Paper]:
    ranked = rank_papers(query, papers)
    query_terms = {term for term in core._keywords(query) if term not in SEARCH_STOPWORDS}
    focused_query = bool(query_terms & AGENT_TERMS) and bool(query_terms & SECURITY_TERMS)
    if focused_query:
        ranked = [paper for paper in ranked if paper.relevance_score >= MIN_FOCUSED_SCORE]

    if len(ranked) < limit:
        fallback_ranked = rank_papers(query, normalize_papers(core.load_demo_papers()))
        seen_ids = {paper.id for paper in ranked}
        for paper in fallback_ranked:
            if paper.id not in seen_ids:
                paper.source = "Demo fallback"
                ranked.append(paper)
                seen_ids.add(paper.id)
            if len(ranked) >= limit:
                break

    return sorted(ranked, key=lambda paper: paper.relevance_score, reverse=True)[:limit]


def export_review(review: core.LiteratureReview, output_path: Path = DEFAULT_OUTPUT_PATH) -> str:
    markdown = to_markdown(review)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def to_markdown(review: core.LiteratureReview) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Literature Review: {review.query}",
        "",
        f"- Forschungsfrage: {review.query}",
        f"- Exportdatum: {generated_at}",
        f"- Paper reviewed: {len(review.papers)}",
        "- Quellen: live arXiv oder Semantic Scholar, mit lokalem Cache als Fallback",
        "- Datenbasis: Paper-Metadaten und Abstracts, keine PDF-Volltextanalyse",
        "- Ranking: Titel-Begriffe, Abstract-Begriffe, thematische Naehe zu Agentic AI/Security und Aktualitaet",
        "",
        "## Paper-Liste",
        "",
    ]

    for position, paper in enumerate(review.papers, start=1):
        lines.extend(
            [
                f"{position}. **{paper.title or 'Kein Titel verfuegbar'}**",
                f"   - Score: {paper.relevance_score}",
                f"   - Jahr: {_display_year(paper.year)}",
                f"   - Autoren: {_display_authors(paper.authors)}",
                f"   - Quelle: {paper.source or 'Keine Quelle verfuegbar'}",
                f"   - Link: {paper.url or 'Kein Link verfuegbar'}",
                "",
            ]
        )

    summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
    lines.extend(["## Annotierte Ergebnisse", ""])
    for paper in review.papers:
        summary = summaries_by_id.get(paper.id)
        lines.extend(
            [
                f"### {paper.title or 'Kein Titel verfuegbar'}",
                "",
                f"- Score: {paper.relevance_score}",
                f"- Jahr: {_display_year(paper.year)}",
                f"- Autoren: {_display_authors(paper.authors)}",
                f"- Quelle: {paper.source or 'Keine Quelle verfuegbar'}",
                f"- Link: {paper.url or 'Kein Link verfuegbar'}",
                "",
                "**Abstract:**",
                "",
                paper.abstract or "Kein Abstract verfuegbar.",
                "",
                "**Zusammenfassung:**",
                "",
                summary.contribution if summary else "Keine Zusammenfassung verfuegbar.",
                "",
            ]
        )
        if summary:
            lines.extend(
                [
                    f"**Keywords:** {', '.join(summary.keywords) if summary.keywords else 'Keine Keywords verfuegbar.'}",
                    "",
                    "**Limitationen:**",
                ]
            )
            lines.extend(f"- {limitation}" for limitation in summary.limitations)
            lines.append("")

    return "\n".join(lines)


def save_cache(papers: list[core.Paper], query: str, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"query": query, "papers": [asdict(paper) for paper in papers]}
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cache(cache_path: Path = DEFAULT_CACHE_PATH) -> list[core.Paper]:
    if not cache_path.exists():
        return []
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    return [core.Paper(**paper) for paper in payload.get("papers", [])]


def _mark_cached(papers: list[core.Paper]) -> list[core.Paper]:
    marked: list[core.Paper] = []
    for paper in papers:
        source = paper.source
        if source == "arXiv live":
            source = "arXiv cached"
        elif source == "Semantic Scholar live":
            source = "Semantic Scholar cached"
        marked.append(
            core.Paper(
                id=paper.id,
                title=paper.title,
                abstract=paper.abstract,
                authors=paper.authors,
                year=paper.year,
                source=source,
                url=paper.url,
                citations=paper.citations,
                relevance_score=paper.relevance_score,
            )
        )
    return marked


def _paper_id(url: str, title: str) -> str:
    source = url.rstrip("/").split("/")[-1] if url else title
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")
    return slug or re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _year_from_date(value: str) -> int:
    match = re.match(r"(\d{4})", value)
    if not match:
        return 0
    return int(match.group(1))


def _display_authors(authors: list[str]) -> str:
    clean_authors = [author for author in authors if author]
    return ", ".join(clean_authors) if clean_authors else "Keine Autorenangabe"


def _display_year(year: int) -> str:
    return str(year) if year else "Kein Jahr verfuegbar"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a live or offline literature review.")
    parser.add_argument("query", nargs="?", default=DEFAULT_QUERY)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()

    review = build_review(args.query, limit=args.limit, live=not args.offline)
    export_review(review, args.output)

    print(f"Literature review generated: {args.output.resolve()}")
    print(f"Papers ranked and summarized: {len(review.papers)}")
    for position, paper in enumerate(review.papers, start=1):
        print(f"{position}. {paper.relevance_score:.4f} - {paper.title} [{paper.source}]")


if __name__ == "__main__":
    main()
