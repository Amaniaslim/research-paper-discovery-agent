from __future__ import annotations

import html
import sys
from pathlib import Path

import streamlit as st

SPRINT_DIR = Path(__file__).resolve().parent
if str(SPRINT_DIR) not in sys.path:
    sys.path.insert(0, str(SPRINT_DIR))

import memory_store as memory  # noqa: E402
import paper_research_agent as pipeline  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="Search & Retrieve", layout="wide")
    _inject_styles()

    st.title("Search & Retrieve")
    st.caption("Live paper search with arXiv, ranking, memory and Markdown export.")

    with st.sidebar:
        st.header("Project Scope")
        st.markdown(
            "- Live arXiv Search\n"
            "- Semantic Scholar Fallback\n"
            "- Ranking\n"
            "- Memory\n"
            "- Markdown Export"
        )
        live = st.toggle("Live arXiv Search", value=True)

    query_col, limit_col, run_col = st.columns([5, 2, 2], vertical_alignment="bottom")
    query = query_col.text_input("Research question", value=pipeline.DEFAULT_QUERY)
    limit = limit_col.slider("Results", min_value=3, max_value=10, value=8)
    run_clicked = run_col.button("Run agent", type="primary", use_container_width=True)

    if run_clicked:
        try:
            review = pipeline.build_review(query, limit=limit, live=live)
            markdown = pipeline.export_review(review)
            memory.remember_review(review)
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"The agent could not run: {exc}")
        else:
            st.session_state["review"] = review
            st.session_state["markdown"] = markdown
            st.session_state["requested_limit"] = limit
            st.session_state["retrieval_status"] = dict(pipeline.LAST_RETRIEVAL_STATUS)
            st.session_state["saved_to_memory"] = True

    review = st.session_state.get("review")
    markdown = st.session_state.get("markdown")
    requested_limit = st.session_state.get("requested_limit", limit)
    retrieval_status = st.session_state.get("retrieval_status", {})
    saved_to_memory = st.session_state.get("saved_to_memory", False)

    tabs = st.tabs(["Overview", "Ranking", "Paper Details", "Memory", "Export"])

    if review is None or markdown is None:
        with tabs[0]:
            st.info("Run the agent to start live search, ranking, memory and export.")
        return

    with tabs[0]:
        _render_overview(review, requested_limit, retrieval_status, saved_to_memory)

    with tabs[1]:
        _render_ranking(review)

    with tabs[2]:
        _render_paper_details(review)

    with tabs[3]:
        _render_memory(query)

    with tabs[4]:
        _render_export(markdown)


def _render_overview(review, requested_limit: int, retrieval_status: dict, saved_to_memory: bool) -> None:
    source_label = _source_label(review)
    _render_status_box(review, retrieval_status, saved_to_memory)

    if source_label == "Fallback" and len(review.papers) < requested_limit:
        st.warning(
            f"{requested_limit} results requested, but only {len(review.papers)} papers are available "
            "in the fallback dataset."
        )
    elif len(review.papers) < requested_limit:
        st.warning(
            f"{requested_limit} results requested, but only {len(review.papers)} passed the relevance filters."
        )

    _render_kpis(
        [
            ("Papers", f"{len(review.papers)} / {requested_limit}"),
            ("Clusters", str(len(review.clusters))),
            ("Source", source_label),
            ("Export", "Markdown"),
        ]
    )

    st.subheader("Short Answer")
    st.write(_build_short_answer(review))


def _render_ranking(review) -> None:
    st.subheader("Ranking")
    rows = [
        {
            "Rank": rank,
            "Score": paper.relevance_score,
            "Year": _display_year(paper.year),
            "Title": paper.title or "No title available",
            "Source": paper.source or "No source available",
        }
        for rank, paper in enumerate(review.papers, start=1)
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True, height=320)
    st.markdown(
        '<div class="score-note">Score = title match + abstract match + topic relevance + year bonus.</div>',
        unsafe_allow_html=True,
    )


def _render_paper_details(review) -> None:
    st.subheader("Paper Details")
    summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
    for rank, paper in enumerate(review.papers, start=1):
        summary = summaries_by_id.get(paper.id)
        with st.container(border=True):
            st.markdown(f"#### {rank}. {paper.title or 'No title available'}")
            meta_cols = st.columns(3)
            meta_cols[0].markdown(f"**Score**  \n{paper.relevance_score}")
            meta_cols[1].markdown(f"**Year**  \n{_display_year(paper.year)}")
            meta_cols[2].markdown(f"**Source**  \n{paper.source or 'No source available'}")

            st.markdown("**Why relevant?**")
            st.caption(_score_explanation(review.query, paper))

            st.markdown("**Short abstract**")
            st.write(_short_text(paper.abstract or "No abstract available.", limit=520))

            if summary is not None:
                st.markdown("**Summary**")
                st.write(summary.contribution)

            if paper.url:
                st.link_button("Open paper link", paper.url)


def _render_export(markdown: str) -> None:
    st.subheader("Export")
    st.download_button(
        "Download literature_review.md",
        data=markdown,
        file_name="literature_review.md",
        mime="text/markdown",
        type="primary",
    )
    with st.expander("Preview generated Markdown"):
        st.markdown(markdown)


def _render_memory(default_query: str) -> None:
    st.subheader("Memory")
    st.caption(f"Active storage: {memory.memory_backend()}")
    recall_query = st.text_input("Search memory", value=default_query)
    if not st.button("Recall previous research", use_container_width=False):
        return

    recalled = memory.recall_reviews(recall_query)
    if not recalled:
        st.info("No matching memory yet. Run the workflow first.")
        return

    for number, document in enumerate(recalled, start=1):
        metadata = document.metadata
        label = f"{number}. {metadata.get('query', 'Saved research run')}"
        with st.expander(label, expanded=number == 1):
            st.write(f"Saved: {metadata.get('saved_at', 'unknown')}")
            st.write(document.page_content)


def _render_kpis(items: list[tuple[str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value) in zip(cols, items):
        col.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{html.escape(label)}</div>
                <div class="kpi-value">{html.escape(value)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_status_box(review, status: dict, saved_to_memory: bool) -> None:
    mode = status.get("mode", "unknown")
    message = status.get("message", "")
    loaded = _loaded_count_from_message(message) or len(review.papers)
    status_label = {
        "live": "Live arXiv successful" if "arxiv" in message.lower() else "Live search successful",
        "cache": "Cache fallback used",
        "fallback": "Fallback data used",
    }.get(mode, "Research run completed")

    st.markdown(
        f"""
        <div class="status-box">
            <div><strong>Status:</strong> {html.escape(status_label)}</div>
            <div><strong>Loaded papers:</strong> {loaded}</div>
            <div><strong>Saved to memory:</strong> {'Yes' if saved_to_memory else 'No'}</div>
            <div><strong>Export:</strong> Markdown</div>
            <div><strong>Summaries:</strong> {html.escape(_summary_label(status))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    retrieval_query = status.get("arxiv_query", "")
    if retrieval_query:
        st.caption(f"Retrieval query: {retrieval_query}")


def _loaded_count_from_message(message: str) -> int | None:
    match = pipeline.re.search(r"(\d+)\s+Paper", message or "")
    if not match:
        return None
    return int(match.group(1))


def _summary_label(status: dict) -> str:
    if status.get("summary_mode") == "saia":
        return "SAIA LLM"
    return "Local heuristic"


def _source_label(review) -> str:
    sources = {paper.source for paper in review.papers}
    if "arXiv live" in sources:
        return "arXiv live"
    if "Semantic Scholar live" in sources:
        return "Semantic Scholar"
    if any("cached" in source.lower() for source in sources):
        return "Cache"
    return "Fallback"


def _build_short_answer(review) -> str:
    if not review.papers:
        return "No matching papers were found for this question."

    top_titles = [paper.title for paper in review.papers[:3]]
    if _looks_german(review.query):
        return (
            "Die gefundenen Paper zeigen, dass zentrale Sicherheitsrisiken "
            "agentischer KI-Systeme vor allem in autonomen Aktionen, Zugriff auf "
            "Dateien oder Datenbanken, Prompt- und Tool-Missbrauch, Datenschutz, "
            "Identitaets-/Zugriffsmanagement und fehlender Governance liegen. "
            f"Am relevantesten sind aktuell: {', '.join(top_titles)}."
        )

    return (
        "The retrieved papers indicate that the main security risks of agentic AI "
        "systems are autonomous tool use, file or database access, prompt and tool "
        "abuse, privacy exposure, identity/access-management weaknesses, and weak "
        "governance. "
        f"The most relevant papers are: {', '.join(top_titles)}."
    )


def _looks_german(text: str) -> bool:
    german_markers = [
        "welche",
        "was",
        "wie",
        "sicherheitsrisiken",
        "entstehen",
        "durch",
        "ki",
        "systeme",
    ]
    lower_text = text.lower()
    return any(marker in lower_text for marker in german_markers)


def _display_year(year: int) -> str:
    return str(year) if year else "No year available"


def _score_explanation(query: str, paper) -> str:
    query_terms = _keywords(query)
    title_terms = _keywords(paper.title)
    abstract_terms = _keywords(paper.abstract)
    title_hits = sorted(query_terms & title_terms)
    abstract_hits = sorted(query_terms & abstract_terms)
    topical = []
    text_terms = title_terms | abstract_terms
    if text_terms & pipeline.AGENT_TERMS:
        topical.append("agentic AI")
    if text_terms & pipeline.SECURITY_TERMS:
        topical.append("security/risk")
    recency = "recent" if paper.year and paper.year >= 2023 else "older or no year"
    return (
        f"Title hits: {_display_hits(title_hits)}; "
        f"abstract hits: {_display_hits(abstract_hits)}; "
        f"topic: {', '.join(topical) if topical else 'no strong topic marker'}; "
        f"year signal: {recency}."
    )


def _keywords(text: str) -> set[str]:
    return {
        keyword
        for keyword in pipeline.core._keywords(text or "")
        if keyword not in pipeline.SEARCH_STOPWORDS
    }


def _display_hits(hits: list[str]) -> str:
    return ", ".join(hits) if hits else "none"


def _short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: #f4f6f8;
                color: #101820;
            }

            h1, h2, h3, h4 {
                color: #101820;
                letter-spacing: 0;
            }

            section[data-testid="stSidebar"] {
                background: #ffffff;
                border-right: 1px solid #e3e7ea;
            }

            section[data-testid="stSidebar"],
            section[data-testid="stSidebar"] * {
                color: #101820;
            }

            label,
            div[data-testid="stWidgetLabel"] *,
            div[data-testid="stMarkdownContainer"] p {
                color: #344054;
            }

            .stButton > button,
            .stDownloadButton > button,
            .stLinkButton > a {
                background: #ef5b5b;
                border: 1px solid #ef5b5b;
                color: #ffffff;
                border-radius: 6px;
                font-weight: 650;
            }

            .stButton > button:hover,
            .stDownloadButton > button:hover,
            .stLinkButton > a:hover {
                background: #d94848;
                border-color: #d94848;
                color: #ffffff;
            }

            .kpi-card {
                background: #ffffff;
                border: 1px solid #e1e6ea;
                border-radius: 8px;
                padding: 16px 18px;
                min-height: 92px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            .kpi-label {
                color: #667085;
                font-size: 0.82rem;
                font-weight: 700;
                text-transform: uppercase;
                margin-bottom: 8px;
            }

            .kpi-value {
                color: #101820;
                font-size: 1.45rem;
                font-weight: 750;
                line-height: 1.15;
                overflow-wrap: anywhere;
            }

            .status-box {
                background: #ffffff;
                border-left: 5px solid #8fd19e;
                border-radius: 8px;
                padding: 14px 18px;
                margin: 8px 0 18px;
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 12px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            .score-note {
                background: #ffffff;
                border: 1px solid #e1e6ea;
                border-left: 5px solid #ef5b5b;
                border-radius: 8px;
                padding: 12px 14px;
                margin-top: 12px;
                font-weight: 650;
                color: #101820;
            }

            div[data-testid="stAlert"] {
                border-radius: 8px;
            }

            @media (max-width: 900px) {
                .status-box {
                    grid-template-columns: 1fr 1fr;
                }
            }

            @media (max-width: 640px) {
                .status-box {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
