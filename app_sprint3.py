from __future__ import annotations

import html
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import chunking  # noqa: E402
import memory_store as memory  # noqa: E402
import paper_research_agent as pipeline  # noqa: E402
import pdf_loader  # noqa: E402
import rag_answer  # noqa: E402
import rag_retriever  # noqa: E402
import rag_store  # noqa: E402


PDF_DIR = PROJECT_DIR / "data" / "pdfs"
EXPORT_PATH = PROJECT_DIR / "demo_output" / "sprint3_pdf_rag_answer.md"


def main() -> None:
    st.set_page_config(page_title="PDF-RAG Research Agent", layout="wide")
    _inject_styles()

    pdf_count = len(_list_pdfs())
    chunk_count = len(rag_store.load_all_chunks())
    st.markdown(
        f"""
        <section class="app-hero">
            <div>
                <div class="eyebrow">Sprint 3</div>
                <h1>PDF-RAG Research Agent</h1>
                <p>Von der Live-Paper-Suche zum PDF-Volltext: Finde Paper, prüfe das Ranking und stelle danach Fragen mit konkreten Quellen.</p>
            </div>
            <div class="hero-meta">
                <span>{pdf_count} PDFs</span>
                <span>{chunk_count} Index-Chunks</span>
                <span>{html.escape(rag_store.storage_backend())}</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Sprint-Ziel")
        st.markdown(
            "**Sprint 1:** Offline-MVP mit Ranking, Memory und Markdown Export.\n\n"
            "**Sprint 2:** Live Search mit arXiv, Fallbacks und transparentem Ranking.\n\n"
            "**Sprint 3:** PDF-Volltext analysieren, relevante Textstellen finden und Antworten mit Quellen erzeugen."
        )
        st.divider()
        st.header("Demo-Workflow")
        st.markdown(
            "1. Forschungsfrage eingeben\n"
            "2. Paper suchen und ranken\n"
            "3. PDF hochladen\n"
            "4. PDF indexieren\n"
            "5. Frage an Volltext stellen"
        )
        st.divider()
        st.caption(f"Storage backend: {rag_store.storage_backend()}")
        st.caption(f"PDF folder: {PDF_DIR.relative_to(PROJECT_DIR).as_posix()}")

    tabs = st.tabs(
        [
            "Überblick",
            "Paper-Suche",
            "PDF-RAG Demo",
            "Export & Memory",
        ]
    )

    with tabs[0]:
        _render_overview()

    with tabs[1]:
        _render_discovery_tab()

    with tabs[2]:
        _render_pdf_rag_demo()

    with tabs[3]:
        _render_export_memory()


def _render_overview() -> None:
    pdfs = _list_pdfs()
    chunks = rag_store.load_all_chunks()
    review = st.session_state.get("review")
    next_step = _next_step_label(review, pdfs, chunks)
    _render_kpis(
        [
            ("Gefundene Paper", str(len(review.papers)) if review else "0"),
            ("PDFs", str(len(pdfs))),
            ("Index-Chunks", str(len(chunks))),
            ("Antwort", st.session_state.get("answer_mode", "noch nicht gestellt")),
        ]
    )

    st.info(f"Nächster Schritt: {next_step}")

    st.markdown("### Was diese Demo zeigt")
    intro_cols = st.columns(3)
    with intro_cols[0]:
        st.markdown(
            """
            <div class="info-card">
                <strong>Sprint 1</strong>
                <span>Offline-MVP mit gespeicherten Paper-Daten, Ranking, Memory und Markdown Export.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with intro_cols[1]:
        st.markdown(
            """
            <div class="info-card">
                <strong>Sprint 2</strong>
                <span>Live Paper Search mit arXiv, Fallbacks, Normalisierung und transparentem Ranking.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with intro_cols[2]:
        st.markdown(
            """
            <div class="info-card">
                <strong>Sprint 3</strong>
                <span>PDF-RAG Prototype mit Upload, Index, Frage, Quellen und Markdown Export.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Empfohlener Ablauf")
    st.markdown(
        """
        <div class="workflow-list">
            <div><b>1.</b><span>Paper-Suche starten und Ranking prüfen.</span></div>
            <div><b>2.</b><span>Im PDF-RAG Demo Tab ein PDF hochladen.</span></div>
            <div><b>3.</b><span>Index bauen und eine Frage an den Volltext stellen.</span></div>
            <div><b>4.</b><span>Quellen prüfen und Markdown exportieren.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _next_step_label(review, pdfs: list[Path], chunks: list[dict]) -> str:
    if not review:
        return "Forschungsfrage eingeben und Paper suchen"
    if not pdfs:
        return "PDF eines relevanten Papers hochladen"
    if not chunks:
        return "PDF indexieren"
    if not st.session_state.get("pdf_answer"):
        return "Frage an die indexierten PDFs stellen"
    return "Quellen prüfen und Antwort exportieren"


def _render_discovery_tab() -> None:
    st.subheader("Suche & Ranking")
    st.write(
        "Dieser Teil entspricht dem Sprint-2-Ziel: Live Paper Search, Fallbacks, "
        "Normalisierung, transparentes Ranking, Memory und Markdown Export."
    )
    _render_discovery_controls(key_prefix="tab", compact=False)
    review = st.session_state.get("review")
    if review:
        _render_review_summary(review)


def _render_discovery_controls(key_prefix: str, compact: bool, boxed: bool = True) -> None:
    default_query = st.session_state.get("research_query", pipeline.DEFAULT_QUERY)
    if boxed:
        with st.container(border=True):
            query = _render_research_question_input(key_prefix, default_query)
    else:
        query = _render_research_question_input(key_prefix, default_query)
    if compact:
        limit = 6
        live = True
    else:
        settings_col, live_col = st.columns([1, 1])
        limit = settings_col.slider(
            "Anzahl Paper",
            min_value=3,
            max_value=10,
            value=6,
            key=f"{key_prefix}_paper_limit",
        )
        live = live_col.toggle("Live arXiv Search", value=True, key=f"{key_prefix}_live_search")

    if st.button("Paper suchen und Ranking erstellen", type="primary", key=f"{key_prefix}_run_discovery"):
        try:
            review = pipeline.build_review(query, limit=limit, live=live)
            markdown = pipeline.export_review(review)
            memory.remember_review(review)
        except (OSError, ValueError, KeyError) as exc:
            st.error(f"Die Paper-Suche konnte nicht ausgefuehrt werden: {exc}")
            return

        st.session_state["research_query"] = query
        st.session_state["review"] = review
        st.session_state["markdown"] = markdown
        st.session_state["retrieval_status"] = dict(pipeline.LAST_RETRIEVAL_STATUS)
        st.success("Paper gefunden, gerankt, als Markdown exportiert und in Memory gespeichert.")


def _render_research_question_input(key_prefix: str, default_query: str) -> str:
    st.markdown("#### Forschungsfrage")
    st.caption("Beispiel fuer die Demo: Security risks of agentic AI systems")
    return st.text_area(
        "Forschungsfrage",
        value=default_query,
        height=120,
        key=f"{key_prefix}_research_query",
        label_visibility="collapsed",
    )


def _render_review_summary(review, compact: bool = False) -> None:
    status = st.session_state.get("retrieval_status", {})
    source = _source_label(review)
    _render_kpis(
        [
            ("Paper", str(len(review.papers))),
            ("Cluster", str(len(review.clusters))),
            ("Quelle", source),
            ("Summaries", _summary_label(status)),
        ]
    )
    if status.get("message"):
        st.caption(status["message"])

    rows = [
        {
            "Rank": rank,
            "Score": paper.relevance_score,
            "Year": paper.year or "n/a",
            "Title": paper.title or "No title available",
            "Source": paper.source or "n/a",
        }
        for rank, paper in enumerate(review.papers, start=1)
    ]
    st.dataframe(rows, hide_index=True, use_container_width=True, height=220 if compact else 260)

    if compact:
        with st.expander("Top Paper Details anzeigen", expanded=False):
            _render_paper_details(review, limit=3)
    else:
        st.markdown("### Paper Details")
        _render_paper_details(review)


def _render_paper_details(review, limit: int | None = None) -> None:
    summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
    papers = review.papers[:limit] if limit else review.papers
    for rank, paper in enumerate(papers, start=1):
        summary = summaries_by_id.get(paper.id)
        with st.expander(f"{rank}. {paper.title or 'No title available'}", expanded=rank == 1):
            meta_cols = st.columns(4)
            meta_cols[0].metric("Score", paper.relevance_score)
            meta_cols[1].metric("Year", paper.year or "n/a")
            meta_cols[2].metric("Source", paper.source or "n/a")
            meta_cols[3].metric("Citations", paper.citations or 0)
            st.markdown("**Warum ist dieses Paper relevant?**")
            st.caption(_score_explanation(review.query, paper))
            st.markdown("**Abstract**")
            st.write(_short_text(paper.abstract or "No abstract available.", limit=850))
            if summary:
                st.markdown("**Kurz-Zusammenfassung**")
                st.write(summary.contribution)
                if summary.limitations:
                    st.markdown("**Limitationen aus Abstract**")
                    st.write("; ".join(summary.limitations))
            if paper.url:
                st.link_button("Paper Link öffnen", paper.url)


def _render_pdf_rag_demo() -> None:
    st.subheader("PDF-RAG Demo")
    st.caption("Upload, Index, Frage und Quellen sind hier in einem klaren Ablauf zusammengefasst.")

    step_cols = st.columns(4)
    pdfs = _list_pdfs()
    chunks = rag_store.load_all_chunks()
    step_cols[0].metric("Schritt 1", "PDF bereit" if pdfs else "PDF hochladen")
    step_cols[1].metric("Schritt 2", "Index bereit" if chunks else "Index bauen")
    step_cols[2].metric("Schritt 3", "Antwort bereit" if st.session_state.get("pdf_answer") else "Frage stellen")
    step_cols[3].metric("Schritt 4", "Quellen", str(len(st.session_state.get("retrieved_chunks", []))))

    st.divider()
    st.markdown("### Schritt 1: PDF hochladen")
    _render_upload_controls(key_prefix="rag_demo_upload", boxed=True)
    pdfs = _list_pdfs()
    if pdfs:
        with st.expander("Hochgeladene PDFs", expanded=False):
            for pdf_path in pdfs:
                _render_file_status(pdf_path, status="bereit")

    st.divider()
    st.markdown("### Schritt 2: Index bauen")
    _render_index_controls(key_prefix="rag_demo_index", compact=True, boxed=True)

    st.divider()
    st.markdown("### Schritt 3: Frage stellen")
    _render_question_controls(key_prefix="rag_demo_question", compact=True, boxed=True)

    answer = st.session_state.get("pdf_answer")
    if answer:
        st.markdown("### Antwort")
        mode = st.session_state.get("answer_mode", "unknown")
        st.markdown(
            f'<div class="status-box"><strong>Antwortmodus:</strong> {html.escape(mode)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(answer)

    st.divider()
    st.markdown("### Schritt 4: Quellen anzeigen")
    chunks = st.session_state.get("retrieved_chunks", [])
    if chunks:
        _render_sources_preview(expanded_first=True)
    else:
        st.info("Nach einer Frage erscheinen hier die gefundenen Quellen.")


def _render_upload_controls(key_prefix: str, boxed: bool = True) -> None:
    if boxed:
        with st.container(border=True):
            uploaded_files = _render_file_upload_input(key_prefix)
    else:
        uploaded_files = _render_file_upload_input(key_prefix)
    if uploaded_files:
        for uploaded_file in uploaded_files:
            try:
                saved_path = pdf_loader.save_uploaded_pdf(uploaded_file, PDF_DIR)
            except OSError as exc:
                st.error(f"{uploaded_file.name} konnte nicht gespeichert werden: {exc}")
                continue
            st.success(f"{saved_path.name} gespeichert")


def _render_file_upload_input(key_prefix: str):
    st.markdown("#### Volltext-PDF hochladen")
    st.caption("Nutze hier das PDF zu einem Paper aus dem Ranking. Danach kann der Volltext durchsucht werden.")
    return st.file_uploader(
        "PDF-Dateien auswaehlen",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"{key_prefix}_pdf_upload",
    )


def _render_index_controls(key_prefix: str, compact: bool, boxed: bool = True) -> None:
    pdfs = _list_pdfs()
    if not pdfs:
        st.info("Lade zuerst mindestens eine PDF hoch. Danach wird dieser Schritt aktiv.")
        return

    if boxed:
        with st.container(border=True):
            selected_names, chunk_size, overlap = _render_index_inputs(key_prefix, pdfs, compact)
    else:
        selected_names, chunk_size, overlap = _render_index_inputs(key_prefix, pdfs, compact)

    if st.button("PDF indexieren", type="primary", key=f"{key_prefix}_index_button"):
        selected_paths = [pdf for pdf in pdfs if pdf.name in selected_names]
        if not selected_paths:
            st.warning("Waehle mindestens eine PDF aus.")
            return

        _index_pdf_paths(selected_paths, chunk_size=chunk_size, overlap=overlap)

    stats = st.session_state.get("index_stats")
    if stats:
        _render_kpis(
            [
                ("Indexierte PDFs", str(len(stats["pdfs"]))),
                ("Seiten", str(stats["pages"])),
                ("Index-Chunks", str(stats["chunks"])),
                ("Indexiert um", stats["indexed_at"]),
            ]
        )


def _render_index_inputs(key_prefix: str, pdfs: list[Path], compact: bool) -> tuple[list[str], int, int]:
    st.markdown("#### Index konfigurieren")
    st.caption(f"Storage backend: {rag_store.storage_backend()}")
    selected_names = st.multiselect(
        "PDFs fuer den Index",
        options=[pdf.name for pdf in pdfs],
        default=[pdf.name for pdf in pdfs],
        key=f"{key_prefix}_index_pdfs",
    )
    if compact:
        chunk_size = 1000
        overlap = 150
        st.caption("Demo-Einstellung: 1000 Zeichen pro Chunk, 150 Zeichen Overlap.")
    else:
        chunk_size = st.slider(
            "Chunk size",
            min_value=700,
            max_value=1400,
            value=1000,
            step=50,
            key=f"{key_prefix}_chunk_size",
        )
        overlap = st.slider(
            "Overlap",
            min_value=50,
            max_value=250,
            value=150,
            step=25,
            key=f"{key_prefix}_overlap",
        )
    return selected_names, chunk_size, overlap


def _index_pdf_paths(selected_paths: list[Path], chunk_size: int, overlap: int) -> None:
    total_pages = 0
    total_chunks = 0
    indexed_files = []
    for pdf_path in selected_paths:
        try:
            pages = pdf_loader.extract_pdf_pages(pdf_path)
            chunks = chunking.chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                st.warning(
                    f"{pdf_path.name}: Kein extrahierbarer Text gefunden. "
                    "Textbasierte PDFs funktionieren; gescannte PDFs brauchen OCR."
                )
                continue
            result = rag_store.store_chunks(chunks)
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"Indexierung fuer {pdf_path.name} fehlgeschlagen: {exc}")
            continue

        total_pages += len(pages)
        total_chunks += len(chunks)
        indexed_files.append(pdf_path.name)
        st.success(
            f"{pdf_path.name}: {len(pages)} Seiten, {len(chunks)} Chunks, Backend: {result['backend']}"
        )

    st.session_state["index_stats"] = {
        "pdfs": indexed_files,
        "pages": total_pages,
        "chunks": total_chunks,
        "indexed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    if not indexed_files:
        st.info("Es wurde kein PDF indexiert. Bitte pruefe, ob die PDF echten Text enthaelt.")


def _render_question_controls(key_prefix: str, compact: bool, boxed: bool = True) -> None:
    if not rag_store.load_all_chunks():
        st.info("Erstelle zuerst den Index. Danach kannst du hier deine Frage an den PDF-Volltext eingeben.")
        return

    if boxed:
        with st.container(border=True):
            question, top_k = _render_question_inputs(key_prefix, compact)
    else:
        question, top_k = _render_question_inputs(key_prefix, compact)

    if st.button("Antwort mit Quellen generieren", type="primary", key=f"{key_prefix}_ask_button"):
        if not question.strip():
            st.warning("Gib zuerst eine Frage ein.")
            return

        chunks = rag_retriever.search_relevant_chunks(question, top_k=top_k)
        answer_result = rag_answer.generate_answer(question, chunks)
        st.session_state["pdf_question"] = question
        st.session_state["retrieved_chunks"] = chunks
        st.session_state["pdf_answer"] = answer_result["answer"]
        st.session_state["answer_mode"] = answer_result["mode"]


def _render_question_inputs(key_prefix: str, compact: bool) -> tuple[str, int]:
    st.markdown("#### Frage an den PDF-Volltext")
    st.caption("Die Antwort darf nur auf den indexierten PDF-Quellen basieren und zeigt Seitenreferenzen.")
    question = st.text_area(
        "Deine Frage",
        value=st.session_state.get("pdf_question", "Welche Sicherheitsrisiken werden im Dokument genannt?"),
        height=140,
        key=f"{key_prefix}_question",
        label_visibility="collapsed",
    )
    top_k = 5 if compact else st.slider(
        "Anzahl Quellen",
        min_value=3,
        max_value=5,
        value=5,
        key=f"{key_prefix}_top_k",
    )
    return question, top_k


def _render_sources_preview(expanded_first: bool = False) -> None:
    chunks = st.session_state.get("retrieved_chunks", [])
    if not chunks:
        return
    st.markdown("### Gefundene Quellen")
    for index, chunk in enumerate(chunks, start=1):
        with st.expander(
            f"Quelle {index}",
            expanded=expanded_first and index == 1,
        ):
            st.markdown(
                f"""
                <div class="source-card">
                    <div><strong>PDF:</strong> {html.escape(str(chunk.get("pdf_name", "unknown.pdf")))}</div>
                    <div><strong>Seite:</strong> {html.escape(str(chunk.get("page_number", "n/a")))}</div>
                    <div><strong>Chunk:</strong> {html.escape(str(chunk.get("chunk_id", "n/a")))}</div>
                    <div class="source-excerpt"><strong>Auszug:</strong> {html.escape(_chunk_excerpt(chunk.get("text", "")))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Vollständigen Chunk anzeigen", expanded=False):
                st.write(chunk.get("text", ""))


def _chunk_excerpt(text: str, limit: int = 650) -> str:
    clean_text = " ".join((text or "").split())
    if len(clean_text) <= limit:
        return clean_text
    return clean_text[:limit].rsplit(" ", 1)[0] + "..."


def _render_memory() -> None:
    st.subheader("Memory")
    st.write(
        "Sprint 1 und 2 speichern Research Runs. In Sprint 3 bleibt diese Memory erhalten, "
        "damit fruehere Recherchen wiedergefunden werden koennen."
    )
    st.caption(f"Active storage: {memory.memory_backend()}")
    recall_query = st.text_input(
        "Memory durchsuchen",
        value=st.session_state.get("research_query", pipeline.DEFAULT_QUERY),
    )
    if not st.button("Fruehere Recherchen abrufen", type="primary"):
        return

    recalled = memory.recall_reviews(recall_query)
    if not recalled:
        st.info("Noch keine passende Memory gefunden. Starte zuerst eine Paper-Suche.")
        return

    for number, document in enumerate(recalled, start=1):
        metadata = document.metadata
        label = f"{number}. {metadata.get('query', 'Gespeicherter Research Run')}"
        with st.expander(label, expanded=number == 1):
            st.write(f"Saved: {metadata.get('saved_at', 'unknown')}")
            st.write(document.page_content)


def _render_export_memory() -> None:
    export_col, memory_col = st.columns([1, 1], gap="large")
    with export_col:
        _render_export()
    with memory_col:
        _render_memory()


def _render_export() -> None:
    st.subheader("Export")
    question = st.session_state.get("pdf_question", "")
    answer = st.session_state.get("pdf_answer", "")
    chunks = st.session_state.get("retrieved_chunks", [])
    discovery_markdown = st.session_state.get("markdown", "")
    if not answer and not discovery_markdown:
        st.info("Starte zuerst die Paper-Suche oder stelle eine PDF-Frage. Danach ist der Export verfuegbar.")
        return

    markdown = _build_export_markdown(question, answer, chunks, discovery_markdown)
    if st.button("Markdown Export schreiben", type="primary"):
        EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXPORT_PATH.write_text(markdown, encoding="utf-8")
        st.success(f"Export written to {EXPORT_PATH}")

    st.download_button(
        "Markdown herunterladen",
        data=markdown,
        file_name="sprint3_pdf_rag_answer.md",
        mime="text/markdown",
        use_container_width=True,
    )

    with st.expander("Preview Markdown"):
        st.markdown(markdown)


def _build_export_markdown(
    question: str,
    answer: str,
    chunks: list[dict],
    discovery_markdown: str = "",
) -> str:
    lines = [
        "# Sprint 3 Research Paper Discovery Agent",
        "",
        f"- Exported at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Antwortmodus: {st.session_state.get('answer_mode', 'unknown')}",
        "- Sprint 1 basis: Offline MVP, ranking, memory, Markdown export",
        "- Sprint 2 basis: Live search, fallback, ranking, memory",
        "- Sprint 3 extension: PDF full-text retrieval and grounded answers",
        "",
    ]
    if discovery_markdown:
        lines.extend(
            [
                "## Paper Discovery Result",
                "",
                discovery_markdown,
                "",
            ]
        )

    if not answer:
        return "\n".join(lines)

    lines.extend(
        [
        "## Frage",
        "",
        question,
        "",
        "## Antwort",
        "",
        answer,
        "",
        "## Quellen",
        "",
        ]
    )
    for index, chunk in enumerate(chunks, start=1):
        lines.extend(
            [
                f"### {index}. {chunk['pdf_name']} - page {chunk['page_number']}",
                "",
                f"- Chunk ID: {chunk['chunk_id']}",
                "",
                chunk["text"],
                "",
            ]
        )
    return "\n".join(lines)


def _source_label(review) -> str:
    sources = {paper.source for paper in review.papers}
    if "arXiv live" in sources:
        return "arXiv live"
    if "Semantic Scholar live" in sources:
        return "Semantic Scholar"
    if any("cached" in (source or "").lower() for source in sources):
        return "Cache"
    return "Fallback"


def _summary_label(status: dict) -> str:
    if status.get("summary_mode") == "saia":
        return "SAIA LLM"
    return "Local heuristic"


def _score_explanation(query: str, paper) -> str:
    query_terms = _keywords(query)
    title_terms = _keywords(paper.title)
    abstract_terms = _keywords(paper.abstract)
    title_hits = sorted(query_terms & title_terms)
    abstract_hits = sorted(query_terms & abstract_terms)
    topic_markers = []
    all_terms = title_terms | abstract_terms
    if all_terms & pipeline.AGENT_TERMS:
        topic_markers.append("Agentic AI")
    if all_terms & pipeline.SECURITY_TERMS:
        topic_markers.append("Security/Risk")
    year_signal = "recent" if paper.year and paper.year >= 2023 else "older or no year"
    return (
        f"Title hits: {_display_hits(title_hits)}; "
        f"abstract hits: {_display_hits(abstract_hits)}; "
        f"topic markers: {', '.join(topic_markers) if topic_markers else 'none'}; "
        f"year signal: {year_signal}."
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


def _render_file_status(pdf_path: Path, status: str) -> None:
    size_kb = pdf_path.stat().st_size / 1024
    st.markdown(
        f"""
        <div class="file-card">
            <strong>{html.escape(pdf_path.name)}</strong><br>
            Size: {size_kb:.1f} KB<br>
            Status: {html.escape(status)}
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def _list_pdfs() -> list[Path]:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(PDF_DIR.glob("*.pdf"))


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1320px;
                padding-top: 1.6rem;
                padding-bottom: 3rem;
            }

            .stApp {
                background: #f3f6f9;
                color: #101820;
            }

            h1, h2, h3, h4 {
                color: #101820;
                letter-spacing: 0;
            }

            .app-hero {
                background: #ffffff;
                border: 1px solid #dde5ec;
                border-radius: 8px;
                padding: 28px 30px;
                margin-bottom: 18px;
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                gap: 24px;
                box-shadow: 0 10px 28px rgba(16, 24, 32, 0.07);
            }

            .app-hero h1 {
                margin: 0;
                font-size: 2.35rem;
                line-height: 1.1;
            }

            .app-hero p {
                color: #475467;
                margin: 12px 0 0;
                max-width: 720px;
                font-size: 1rem;
            }

            .eyebrow {
                color: #d94848;
                font-size: 0.78rem;
                font-weight: 800;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 8px;
            }

            .hero-meta {
                display: flex;
                flex-wrap: wrap;
                justify-content: flex-end;
                gap: 8px;
                min-width: 250px;
            }

            .hero-meta span {
                background: #f5f8fb;
                border: 1px solid #dbe4ec;
                border-radius: 999px;
                color: #344054;
                font-size: 0.82rem;
                font-weight: 700;
                padding: 7px 10px;
            }

            section[data-testid="stSidebar"] {
                background: #ffffff;
                border-right: 1px solid #dfe7ee;
            }

            section[data-testid="stSidebar"],
            section[data-testid="stSidebar"] * {
                color: #101820;
            }

            div[data-baseweb="tab-list"] {
                gap: 6px;
                border-bottom: 1px solid #dfe7ee;
                margin-bottom: 18px;
            }

            button[data-baseweb="tab"] {
                background: #ffffff;
                border: 1px solid #dfe7ee;
                border-bottom: 0;
                border-radius: 8px 8px 0 0;
                color: #344054;
                font-weight: 750;
                padding: 8px 14px;
            }

            button[data-baseweb="tab"] p {
                color: #344054;
                font-weight: 750;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                background: #101820;
                border-color: #101820;
            }

            button[data-baseweb="tab"][aria-selected="true"] p {
                color: #ffffff;
            }

            .stButton > button,
            .stDownloadButton > button {
                background: #ef5b5b;
                border: 1px solid #ef5b5b;
                color: #ffffff;
                border-radius: 6px;
                font-weight: 650;
                min-height: 42px;
            }

            .stButton > button:hover,
            .stDownloadButton > button:hover {
                background: #d94848;
                border-color: #d94848;
                color: #ffffff;
            }

            .stButton > button[kind="primary"],
            .stDownloadButton > button[kind="primary"] {
                width: 100%;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                background: #ffffff;
                border-color: #d8e2eb;
                border-radius: 8px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            div[data-baseweb="textarea"],
            div[data-baseweb="input"],
            div[data-testid="stFileUploaderDropzone"] {
                background: #ffffff;
                border-color: #cfd9e3;
                color: #101820;
            }

            div[data-baseweb="textarea"] textarea,
            div[data-baseweb="input"] input {
                background: #ffffff;
                color: #101820;
                font-size: 0.98rem;
                line-height: 1.45;
            }

            div[data-baseweb="textarea"] textarea::placeholder,
            div[data-baseweb="input"] input::placeholder {
                color: #667085;
            }

            div[data-testid="stFileUploaderDropzone"] {
                background: #ffffff !important;
                border: 1px dashed #9fb2c3 !important;
                border-radius: 8px !important;
                min-height: 124px;
            }

            div[data-testid="stFileUploaderDropzone"] * {
                color: #101820 !important;
            }

            .kpi-card,
            .file-card,
            .status-box {
                background: #ffffff;
                border: 1px solid #e1e6ea;
                border-radius: 8px;
                padding: 14px 16px;
                margin-bottom: 12px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            .kpi-card {
                min-height: 92px;
            }

            .file-card {
                color: #344054;
                line-height: 1.55;
            }

            .status-box {
                border-left: 5px solid #8fd19e;
            }

            .kpi-label {
                color: #667085;
                font-size: 0.78rem;
                font-weight: 750;
                text-transform: uppercase;
                margin-bottom: 8px;
            }

            .kpi-value {
                color: #101820;
                font-size: 1.25rem;
                font-weight: 750;
                overflow-wrap: anywhere;
            }

            .demo-command {
                background: #101820;
                border-radius: 8px;
                color: #ffffff;
                display: grid;
                gap: 18px;
                grid-template-columns: minmax(280px, 0.7fr) 1fr;
                margin: 18px 0 24px;
                padding: 18px 20px;
            }

            .demo-command span {
                color: #ffb4b4;
                display: block;
                font-size: 0.75rem;
                font-weight: 850;
                text-transform: uppercase;
            }

            .demo-command strong {
                color: #ffffff;
                display: block;
                font-size: 1.2rem;
                line-height: 1.25;
                margin-top: 4px;
            }

            .demo-command p {
                color: #d9e2ea;
                margin: 0;
                line-height: 1.5;
            }

            .simple-step {
                align-items: center;
                background: #ffffff;
                border: 1px solid #d8e2eb;
                border-left: 6px solid #b7c6d4;
                border-radius: 8px;
                display: grid;
                gap: 14px;
                grid-template-columns: 38px 1fr auto;
                margin: 22px 0 12px;
                padding: 16px 18px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            .simple-step-active {
                border-left-color: #ef5b5b;
            }

            .simple-step-complete {
                border-left-color: #2e9f63;
            }

            .simple-step-number {
                align-items: center;
                background: #101820;
                border-radius: 999px;
                color: #ffffff;
                display: flex;
                font-weight: 850;
                height: 34px;
                justify-content: center;
                width: 34px;
            }

            .simple-step-active .simple-step-number {
                background: #ef5b5b;
            }

            .simple-step-complete .simple-step-number {
                background: #2e9f63;
            }

            .simple-step-copy strong {
                color: #101820;
                display: block;
                font-size: 1.04rem;
                line-height: 1.25;
            }

            .simple-step-copy span {
                color: #475467;
                display: block;
                font-size: 0.9rem;
                line-height: 1.4;
                margin-top: 4px;
            }

            .simple-step-state {
                background: #f1f5f9;
                border: 1px solid #d8e2eb;
                border-radius: 999px;
                color: #344054;
                font-size: 0.78rem;
                font-weight: 850;
                padding: 6px 10px;
                white-space: nowrap;
            }

            .simple-step-active .simple-step-state {
                background: #fff0f0;
                border-color: #ffc8c8;
                color: #c73737;
            }

            .simple-step-complete .simple-step-state {
                background: #edf9f2;
                border-color: #b9e4c9;
                color: #247a49;
            }

            .workflow-list {
                display: grid;
                gap: 10px;
                margin-top: 12px;
            }

            .workflow-list div {
                align-items: flex-start;
                background: #ffffff;
                border: 1px solid #dde5ec;
                border-radius: 8px;
                display: grid;
                grid-template-columns: 34px 1fr;
                gap: 12px;
                padding: 13px 15px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.03);
            }

            .workflow-list b {
                align-items: center;
                background: #101820;
                border-radius: 999px;
                color: #ffffff;
                display: flex;
                font-size: 0.82rem;
                font-weight: 800;
                height: 28px;
                justify-content: center;
                width: 28px;
            }

            .workflow-list span {
                color: #344054;
                line-height: 1.45;
                padding-top: 3px;
            }

            .source-card {
                background: #ffffff;
                border: 1px solid #dde5ec;
                border-left: 5px solid #8fb3d9;
                border-radius: 8px;
                color: #344054;
                display: grid;
                gap: 8px;
                padding: 14px 16px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.03);
            }

            .source-card strong {
                color: #101820;
            }

            .source-excerpt {
                border-top: 1px solid #edf2f7;
                line-height: 1.5;
                margin-top: 4px;
                padding-top: 10px;
            }

            .demo-banner {
                background: #101820;
                border-radius: 8px;
                color: #ffffff;
                display: grid;
                gap: 12px;
                grid-template-columns: minmax(260px, 0.75fr) 1fr;
                margin: 18px 0 24px;
                padding: 18px 20px;
            }

            .demo-banner strong {
                color: #ffffff;
                display: block;
                font-size: 1.18rem;
                line-height: 1.25;
                margin-top: 4px;
            }

            .demo-banner p {
                color: #d9e2ea;
                margin: 0;
                line-height: 1.5;
            }

            .demo-label {
                color: #ffb4b4;
                font-size: 0.74rem;
                font-weight: 800;
                text-transform: uppercase;
            }

            .demo-stage {
                align-items: flex-start;
                background: #ffffff;
                border: 1px solid #d8e2eb;
                border-left: 6px solid #b7c6d4;
                border-radius: 8px;
                display: flex;
                gap: 16px;
                margin: 20px 0 12px;
                padding: 18px 20px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.04);
            }

            .demo-stage-active {
                border-left-color: #ef5b5b;
            }

            .demo-stage-complete {
                border-left-color: #3da66b;
            }

            .stage-number {
                align-items: center;
                background: #101820;
                border-radius: 999px;
                color: #ffffff;
                display: flex;
                flex: 0 0 36px;
                font-weight: 850;
                height: 36px;
                justify-content: center;
                width: 36px;
            }

            .demo-stage-active .stage-number {
                background: #ef5b5b;
            }

            .demo-stage-complete .stage-number {
                background: #3da66b;
            }

            .stage-title-row {
                align-items: center;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: space-between;
            }

            .stage-title-row h3 {
                font-size: 1.22rem;
                margin: 0;
            }

            .stage-title-row span {
                background: #eef4f8;
                border: 1px solid #d8e2eb;
                border-radius: 999px;
                color: #344054;
                font-size: 0.78rem;
                font-weight: 800;
                padding: 5px 9px;
            }

            .demo-stage-active .stage-title-row span {
                background: #fff0f0;
                border-color: #ffc8c8;
                color: #c73737;
            }

            .demo-stage-complete .stage-title-row span {
                background: #edf9f2;
                border-color: #b9e4c9;
                color: #247a49;
            }

            .demo-stage p {
                color: #475467;
                margin: 8px 0 0;
                line-height: 1.45;
            }

            .workflow-strip {
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 10px;
                margin-top: 18px;
            }

            .workflow-strip div {
                background: #ffffff;
                border: 1px solid #dde5ec;
                border-radius: 8px;
                padding: 14px;
                min-height: 86px;
            }

            .workflow-strip strong {
                display: block;
                color: #101820;
                font-size: 0.95rem;
                margin-bottom: 6px;
            }

            .workflow-strip span {
                color: #667085;
                font-size: 0.86rem;
                line-height: 1.35;
            }

            .step-card {
                background: #101820;
                border-radius: 8px;
                color: #ffffff;
                display: flex;
                gap: 12px;
                margin: 8px 0 14px;
                min-height: 96px;
                padding: 16px;
            }

            .step-number {
                align-items: center;
                background: #ef5b5b;
                border-radius: 999px;
                display: flex;
                flex: 0 0 32px;
                font-weight: 800;
                height: 32px;
                justify-content: center;
                width: 32px;
            }

            .step-card strong {
                color: #ffffff;
                display: block;
                font-size: 1rem;
                margin-bottom: 6px;
            }

            .step-card span {
                color: #d9e2ea;
                display: block;
                font-size: 0.9rem;
                line-height: 1.4;
            }

            div[data-testid="stAlert"] {
                border-radius: 8px;
            }

            @media (max-width: 900px) {
                .app-hero {
                    align-items: flex-start;
                    flex-direction: column;
                }

                .hero-meta {
                    justify-content: flex-start;
                }

                .workflow-strip {
                    grid-template-columns: 1fr 1fr;
                }

                .demo-banner {
                    grid-template-columns: 1fr;
                }

                .demo-command {
                    grid-template-columns: 1fr;
                }

                .simple-step {
                    grid-template-columns: 38px 1fr;
                }

                .simple-step-state {
                    grid-column: 2;
                    justify-self: start;
                }
            }

            @media (max-width: 640px) {
                .app-hero {
                    padding: 22px;
                }

                .app-hero h1 {
                    font-size: 1.85rem;
                }

                .workflow-strip {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
