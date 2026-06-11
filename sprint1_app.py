from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

SPRINT_DIR = Path(__file__).resolve().parent
if str(SPRINT_DIR) not in sys.path:
    sys.path.insert(0, str(SPRINT_DIR))

import memory_store as memory  # noqa: E402
import review_core as pipeline  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="Sprint 1 - Literature Discovery MVP", layout="wide")

    st.title("Sprint 1: Literature Discovery MVP")
    st.caption(
        "Offline-Demo: gespeicherte Paper-Metadaten werden fuer eine Forschungsfrage "
        "gerankt, aus Abstracts zusammengefasst und als Review exportiert."
    )

    with st.sidebar:
        st.header("Sprint Scope")
        st.write("In Sprint 1 implementiert:")
        st.markdown(
            "- Strukturierte Paper-Daten\n"
            "- Relevanz-Ranking\n"
            "- Abstract-basierte Kurzfassung\n"
            "- Markdown-Export\n"
            "- ChromaDB Memory"
        )
        st.write("Naechster Sprint:")
        st.markdown("- Live-API-Suche\n- LLM-Zusammenfassung\n- PDF-RAG")

    query = st.text_input("Forschungsfrage", value=pipeline.DEFAULT_QUERY)
    limit = st.slider("Anzahl der Ergebnisse", min_value=1, max_value=5, value=5)

    if st.button("MVP ausfuehren", type="primary"):
        try:
            review = pipeline.build_review(query, limit=limit)
            markdown = pipeline.export_review(review)
            memory.remember_review(review)
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"Demo konnte nicht ausgefuehrt werden: {exc}")
        else:
            st.session_state["sprint1_review"] = review
            st.session_state["sprint1_markdown"] = markdown
            st.success("Review exportiert und als ChromaDB Memory gespeichert.")

    review = st.session_state.get("sprint1_review")
    markdown = st.session_state.get("sprint1_markdown")
    if review is None or markdown is None:
        st.info("Klicke auf 'MVP ausfuehren', um den Sprint-1-Workflow live zu zeigen.")
    else:
        _render_review(review, markdown)

    st.divider()
    _render_memory(query)


def _render_review(review, markdown: str) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Analysierte Paper", len(review.papers))
    col2.metric("Themencluster", len(review.clusters))
    col3.metric("Exportformat", "Markdown")

    st.subheader("Ranking")
    rows = [
        {
            "Rang": rank,
            "Score": paper.relevance_score,
            "Jahr": paper.year,
            "Titel": paper.title,
            "Quelle": paper.source,
        }
        for rank, paper in enumerate(review.papers, start=1)
    ]
    st.dataframe(rows, width="stretch", hide_index=True)

    st.subheader("Automatisch extrahierte Zusammenfassungen")
    summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
    for paper in review.papers:
        summary = summaries_by_id[paper.id]
        with st.expander(paper.title, expanded=paper == review.papers[0]):
            st.write(summary.contribution)
            st.write("Keywords: " + ", ".join(summary.keywords))
            st.write("Limitationen: " + " ".join(summary.limitations))

    st.subheader("Export")
    st.download_button(
        "review.md herunterladen",
        data=markdown,
        file_name="sprint1_review.md",
        mime="text/markdown",
    )
    with st.expander("Generiertes Markdown anzeigen"):
        st.markdown(markdown)


def _render_memory(default_query: str) -> None:
    st.header("Persistent Memory mit ChromaDB")
    st.caption(
        "Jeder ausgefuehrte Review wird als Vektor gespeichert. "
        "Damit findet der Agent nach einem Neustart verwandte fruehere Recherchen wieder."
    )
    recall_query = st.text_input("Memory durchsuchen", value=default_query)
    if not st.button("Fruehere Recherchen abrufen"):
        return

    recalled = memory.recall_reviews(recall_query)
    if not recalled:
        st.info("Noch keine passende Memory vorhanden. Fuehre zuerst den MVP aus.")
        return

    for number, document in enumerate(recalled, start=1):
        metadata = document.metadata
        label = f"{number}. {metadata.get('query', 'Gespeicherte Recherche')}"
        with st.expander(label, expanded=number == 1):
            st.write(f"Gespeichert: {metadata.get('saved_at', 'unbekannt')}")
            st.write(document.page_content)


if __name__ == "__main__":
    main()
