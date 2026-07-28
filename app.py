from __future__ import annotations

import csv
import html
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

import chunking  # noqa: E402
import embedding_config  # noqa: E402
import export_utils  # noqa: E402
import history_store  # noqa: E402
import memory_store as memory  # noqa: E402
import ocr_service  # noqa: E402
import paper_research_agent as pipeline  # noqa: E402
import pdf_loader  # noqa: E402
import rag_answer  # noqa: E402
import rag_retriever  # noqa: E402
import rag_store  # noqa: E402

PDF_DIR = PROJECT_DIR / "data" / "pdfs"
EXPORT_PATH = PROJECT_DIR / "demo_output" / "pdf_rag_answer.md"
CSV_EXPORT_PATH = PROJECT_DIR / "demo_output" / "sources.csv"
XLSX_EXPORT_PATH = PROJECT_DIR / "demo_output" / "sources.xlsx"
SCALABILITY_LOG_PATH = PROJECT_DIR / "demo_output" / "scalability_log.csv"
LARGE_PDF_THRESHOLD = 100


def main() -> None:
    st.set_page_config(page_title="Research Paper Discovery Agent", layout="wide")
    _inject_styles()

    pdf_count = len(_list_pdfs())
    chunk_count = len(rag_store.load_all_chunks())
    st.markdown(
        f"""
        <section class="app-hero">
            <div>
                <div class="eyebrow">AI-assisted literature discovery</div>
                <h1>Research Paper Discovery Agent</h1>
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
        _render_sidebar_history()
        st.divider()
        st.header("Research Workflow")
        st.markdown(
            "1. Forschungsfrage eingeben\n"
            "2. Paper suchen und ranken\n"
            "3. PDF hochladen\n"
            "4. PDF indexieren\n"
            "5. Frage an Volltext stellen"
        )
        st.divider()
        st.caption(f"Storage backend: {rag_store.storage_backend()}")
        st.caption(f"Embedding model: {embedding_config.active_model_label()}")
        st.caption(f"OCR mode: {ocr_service.get_ocr_mode()}")
        st.caption(f"PDF folder: {PDF_DIR.relative_to(PROJECT_DIR).as_posix()}")

    tabs = st.tabs(
        [
            "Overview",
            "Paper Search",
            "PDF Knowledge Base",
            "Memory & Export",
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


# Logical session keys that make up one saved session snapshot.
_HISTORY_PAYLOAD_KEYS = (
    "research_query",
    "pdf_question",
    "pdf_answer",
    "answer_mode",
    "retrieved_chunks",
    "retrieval_seconds",
    "selected_sections",
    "index_stats",
    "markdown",
)

# Session keys cleared when starting a new research or loading another session.
_SESSION_KEYS_TO_RESET = (
    "review",
    "retrieval_status",
    *_HISTORY_PAYLOAD_KEYS,
)

# Widget keys that mirror restored values; cleared so inputs re-init from state.
_WIDGET_KEYS_TO_RESET = (
    "tab_research_query",
    "rag_demo_question_question",
)


def _reset_session() -> None:
    for key in _SESSION_KEYS_TO_RESET:
        st.session_state.pop(key, None)
    for key in _WIDGET_KEYS_TO_RESET:
        st.session_state.pop(key, None)
    st.session_state.pop("current_history_id", None)


def _load_history_entry(entry: dict) -> None:
    """Restore a saved session snapshot into session state."""
    for key in _SESSION_KEYS_TO_RESET:
        st.session_state.pop(key, None)
    for key in _WIDGET_KEYS_TO_RESET:
        st.session_state.pop(key, None)
    for key, value in (entry.get("payload") or {}).items():
        st.session_state[key] = value
    st.session_state["current_history_id"] = entry.get("id")


def _save_current_history(title: str) -> None:
    """Snapshot the current session into the history store (create or update)."""
    payload = {key: st.session_state[key] for key in _HISTORY_PAYLOAD_KEYS if key in st.session_state}
    entry_id = history_store.upsert_entry(
        st.session_state.get("current_history_id"),
        (title or "Recherche").strip(),
        payload,
    )
    st.session_state["current_history_id"] = entry_id


def _render_sidebar_history() -> None:
    """Chat-style sidebar: a 'new research' button plus a reopenable history."""
    if st.button("＋ Neue Recherche", key="sidebar_new_research", use_container_width=True):
        _reset_session()
        st.rerun()

    st.header("Verlauf")
    entries = history_store.list_entries()
    if not entries:
        st.caption("Noch kein Verlauf. Deine Suchen und Fragen erscheinen hier automatisch.")
        return

    editing_id = st.session_state.get("history_editing_id")
    active_id = st.session_state.get("current_history_id")
    for entry in entries:
        entry_id = str(entry.get("id"))
        if editing_id == entry_id:
            new_title = st.text_input(
                "Titel bearbeiten",
                value=entry.get("title", ""),
                key=f"hist_rename_input_{entry_id}",
                label_visibility="collapsed",
            )
            save_col, cancel_col = st.columns(2)
            if save_col.button("Speichern", key=f"hist_save_{entry_id}", use_container_width=True):
                history_store.rename_entry(entry_id, new_title.strip())
                st.session_state.pop("history_editing_id", None)
                st.rerun()
            if cancel_col.button("Abbrechen", key=f"hist_cancel_{entry_id}", use_container_width=True):
                st.session_state.pop("history_editing_id", None)
                st.rerun()
            continue

        open_col, edit_col, del_col = st.columns([6, 1, 1])
        marker = "• " if entry_id == active_id else ""
        title_label = marker + _short_text(str(entry.get("title", "Recherche")), limit=28)
        if open_col.button(
            title_label,
            key=f"hist_open_{entry_id}",
            use_container_width=True,
            help=f"Geöffnet: {entry.get('updated_at', '')}",
        ):
            _load_history_entry(entry)
            st.rerun()
        if edit_col.button("✏️", key=f"hist_edit_{entry_id}", help="Umbenennen"):
            st.session_state["history_editing_id"] = entry_id
            st.rerun()
        if del_col.button("🗑️", key=f"hist_del_{entry_id}", help="Löschen"):
            history_store.delete_entry(entry_id)
            if active_id == entry_id:
                st.session_state.pop("current_history_id", None)
            st.session_state.pop("history_editing_id", None)
            st.rerun()


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

    st.markdown("### Was dieser Agent kann")
    intro_cols = st.columns(3)
    with intro_cols[0]:
        st.markdown(
            """
            <div class="info-card">
                <strong>Paper-Suche & Ranking</strong>
                <span>Live-Suche über arXiv mit Fallbacks, Normalisierung und transparentem Ranking.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with intro_cols[1]:
        st.markdown(
            """
            <div class="info-card">
                <strong>PDF-Volltext (RAG)</strong>
                <span>PDFs hochladen, indexieren und Fragen an den Volltext mit relevanten Textstellen stellen.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with intro_cols[2]:
        st.markdown(
            """
            <div class="info-card">
                <strong>Quellen & Export</strong>
                <span>Antworten mit Seiten- und Chunk-Quellen, Export als Markdown, CSV und Excel.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Empfohlener Ablauf")
    st.markdown(
        """
        <div class="workflow-list">
            <div><b>1.</b><span>Paper-Suche starten und Ranking prüfen.</span></div>
            <div><b>2.</b><span>In der PDF Knowledge Base ein PDF hochladen.</span></div>
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
        "Live Paper Search mit Fallbacks, Normalisierung, transparentem Ranking, "
        "Memory und Markdown Export."
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
        live = live_col.toggle(
            "Live arXiv Search aktivieren",
            value=True,
            key=f"{key_prefix}_live_search_toggle_clean",
        )
        live_col.markdown(
            f'<div class="toggle-status {"toggle-on" if live else "toggle-off"}">Live arXiv Search: {"aktiviert" if live else "deaktiviert"}</div>',
            unsafe_allow_html=True,
        )

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
        _save_current_history(query)
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
    source = _display_source_label(_source_label(review))
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
            "Source": _display_source_label(paper.source),
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
        st.markdown(f"**{rank}. {paper.title or 'No title available'}**")
        meta_cols = st.columns(4)
        meta_cols[0].metric("Score", paper.relevance_score)
        meta_cols[1].metric("Jahr", paper.year or "n/a")
        meta_cols[2].metric("Quelle", _display_source_label(paper.source))
        if paper.url:
            meta_cols[3].link_button("Paper öffnen", paper.url)
        else:
            meta_cols[3].markdown('<div class="disabled-link-button">Kein Link</div>', unsafe_allow_html=True)

        with st.expander("Details anzeigen", expanded=False):
            st.markdown("**Warum ist dieses Paper relevant?**")
            st.caption(_score_explanation(review.query, paper))
            st.markdown("**Abstract**")
            st.write(_short_text(paper.abstract or "No abstract available.", limit=650))
            if summary:
                st.markdown("**Kurz-Zusammenfassung**")
                st.write(_short_text(summary.contribution, limit=450))
                if summary.limitations:
                    st.markdown("**Limitationen aus Abstract**")
                    st.write("; ".join(summary.limitations))


def _render_pdf_rag_demo() -> None:
    st.subheader("PDF Knowledge Base")
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
    _render_uploaded_pdf_list(pdfs)

    st.divider()
    st.markdown("### Schritt 2: Index bauen")
    _render_index_controls(key_prefix="rag_demo_index", compact=True, boxed=True)

    st.divider()
    st.markdown("### Schritt 3: Frage stellen")
    _render_question_controls(key_prefix="rag_demo_question", compact=True, boxed=True)

    answer = st.session_state.get("pdf_answer")
    if answer:
        answer = _prepare_answer_for_display(answer, st.session_state.get("retrieved_chunks", []))
        st.session_state["pdf_answer"] = answer
        st.markdown("### Antwort")
        mode = st.session_state.get("answer_mode", "unknown")
        mode_label = "lokaler Fallback" if mode == "fallback" else ("SAIA" if mode == "saia" else mode)
        mode_note = (
            "Die Antwort wurde aus den gefundenen Chunks extrahiert, nicht frei generiert."
            if mode == "fallback"
            else "Die Antwort wurde mit dem konfigurierten LLM aus den gefundenen Quellen erzeugt."
        )
        st.markdown(
            f"""
            <div class="status-box">
                <strong>Antwortmodus: {html.escape(mode_label)}</strong>
                <span>{html.escape(mode_note)}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        short_answer = _build_short_answer(
            st.session_state.get("pdf_question", ""),
            answer,
            st.session_state.get("retrieved_chunks", []),
        )
        if short_answer:
            st.markdown("#### Kurzantwort")
            st.markdown(short_answer)
        st.markdown("#### Details")
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
        processed = st.session_state.setdefault("_processed_uploads", set())
        newly_saved = []
        for uploaded_file in uploaded_files:
            signature = f"{uploaded_file.name}:{uploaded_file.size}"
            if signature in processed:
                continue
            try:
                saved_path = pdf_loader.save_uploaded_pdf(uploaded_file, PDF_DIR)
            except OSError as exc:
                st.error(f"{uploaded_file.name} konnte nicht gespeichert werden: {exc}")
                continue
            processed.add(signature)
            newly_saved.append(saved_path.name)
            st.session_state["last_uploaded_pdfs"] = [saved_path.name]
            size_kb = saved_path.stat().st_size / 1024
            st.markdown(
                f"""
                <div class="upload-success">
                    <strong>PDF erfolgreich hochgeladen</strong>
                    <span>Datei: {html.escape(saved_path.name)}</span>
                    <span>Größe: {size_kb:.1f} KB</span>
                    <span>Status: bereit</span>
                    <span>Nächster Schritt: PDF unten zum Indexieren auswählen.</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_file_upload_input(key_prefix: str):
    st.markdown("#### PDF-Datei hochladen")
    st.markdown(
        """
        <div class="upload-cta">
            <strong>PDF auswählen oder hier ablegen</strong>
            <span>Nur PDF · max. 200 MB pro Datei</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Ziehe eine PDF-Datei hierher oder klicke, um sie auszuwählen.")
    st.markdown('<div class="upload-hint">Nur PDF · max. 200 MB pro Datei</div>', unsafe_allow_html=True)
    return st.file_uploader(
        "PDF-Dateien hochladen",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"{key_prefix}_pdf_upload",
    )


def _render_uploaded_pdf_list(pdfs: list[Path]) -> None:
    st.markdown("#### Hochgeladene PDFs")
    if not pdfs:
        st.info("Noch keine PDF hochgeladen. Wähle oben eine PDF-Datei aus oder ziehe sie in die Upload-Box.")
        return
    for pdf_path in pdfs:
        _render_file_status(pdf_path, status="bereit")


def _render_index_controls(key_prefix: str, compact: bool, boxed: bool = True) -> None:
    pdfs = _list_pdfs()
    if not pdfs:
        st.info("Lade zuerst mindestens eine PDF hoch. Danach wird dieser Schritt aktiv.")
        return

    if boxed:
        with st.container(border=True):
            config = _render_index_inputs(key_prefix, pdfs, compact)
    else:
        config = _render_index_inputs(key_prefix, pdfs, compact)

    selected_names = config["selected_names"]
    selected_paths = [pdf for pdf in pdfs if pdf.name in selected_names]
    _render_index_summary(selected_names, config["chunk_size"], config["overlap"], config["enable_ocr"])
    if not selected_paths:
        st.warning("Bitte zuerst mindestens eine PDF auswählen.")

    if st.button("PDF indexieren", type="primary", key=f"{key_prefix}_index_button", disabled=not selected_paths):
        _index_pdf_paths(
            selected_paths,
            chunk_size=config["chunk_size"],
            overlap=config["overlap"],
            enable_ocr=config["enable_ocr"],
            ocr_provider=config["ocr_provider"],
            page_start=config["page_start"],
            page_end=config["page_end"],
        )

    stats = st.session_state.get("index_stats")
    if stats:
        _render_kpis(
            [
                ("Indexierte PDFs", str(len(stats["pdfs"]))),
                ("Seiten", str(stats["pages"])),
                ("Index-Chunks", str(stats["chunks"])),
                ("OCR-Seiten", str(stats["ocr_pages"])),
                ("Backend", str(stats.get("backend", rag_store.storage_backend()))),
            ]
        )
        _render_kpis(
            [
                ("Seitenbereich", str(stats.get("page_range", "ganzes PDF"))),
                ("Embedding", str(stats.get("embedding_model", "n/a"))),
                ("OCR-Modus", str(stats.get("ocr_mode", "disabled"))),
                ("Indexzeit", f"{stats.get('index_seconds', 0):.2f}s"),
                ("Indexiert um", stats["indexed_at"]),
            ]
        )


def _render_index_inputs(key_prefix: str, pdfs: list[Path], compact: bool) -> dict:
    st.markdown("#### Index konfigurieren")
    st.caption(f"Storage backend: {rag_store.storage_backend()}")
    st.caption(f"Embedding model: {embedding_config.active_model_label()}")
    st.markdown('<div class="index-step-label index-step-primary">1. PDFs für den Index auswählen</div>', unsafe_allow_html=True)
    selected_names = st.multiselect(
        "PDFs zum Indexieren auswählen",
        options=[pdf.name for pdf in pdfs],
        default=_default_selected_pdf_names(pdfs),
        placeholder="Eine oder mehrere PDFs auswählen",
        format_func=_short_filename,
        key=f"{key_prefix}_index_pdfs",
        help="Wähle eine oder mehrere hochgeladene PDFs aus. Die ausgewählten Dateien werden indexiert.",
    )
    st.caption("Wähle die PDFs aus, die durchsucht werden sollen.")
    page_start, page_end = _render_page_range_inputs(key_prefix, pdfs, selected_names)
    if compact:
        chunk_size = 1000
        overlap = 150
        st.caption("Standardeinstellung: 1000 Zeichen pro Chunk, 150 Zeichen Overlap.")
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
    st.markdown('<div class="index-step-label">3. OCR optional aktivieren</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ocr-panel">
            <div class="ocr-panel-title">OCR-Fallback für gescannte Seiten</div>
            <div class="ocr-panel-copy">Wenn eine Seite keinen extrahierbaren Text enthält, wird optional OCR versucht (Tesseract lokal oder Baidu Unlimited-OCR).</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="ocr-panel-note">OCR wird nur genutzt, wenn eine PDF-Seite keinen extrahierbaren Text enthält.</div>',
        unsafe_allow_html=True,
    )
    _render_scanned_pdf_hint(pdfs, selected_names)
    configured_mode = ocr_service.get_ocr_mode()
    enable_ocr = st.toggle(
        "OCR für gescannte Seiten aktivieren",
        value=configured_mode != ocr_service.MODE_DISABLED,
        key=f"{key_prefix}_enable_ocr_toggle_clean",
        help=f"Voreinstellung aus OCR_MODE={configured_mode}.",
    )
    st.markdown(
        f'<div class="ocr-status toggle-status {"toggle-on" if enable_ocr else "toggle-off"}">OCR: {"aktiviert" if enable_ocr else "deaktiviert"}</div>',
        unsafe_allow_html=True,
    )
    ocr_backend_label = "Tesseract lokal"
    if enable_ocr:
        backend_options = [
            "Tesseract lokal — lokale OCR, wenn installiert",
            "Baidu Unlimited-OCR Server — externer OCR-kompatibler Endpoint",
        ]
        ocr_backend_label = st.selectbox(
            "OCR-Backend",
            options=backend_options,
            index=1 if configured_mode == ocr_service.MODE_UNLIMITED else 0,
            key=f"{key_prefix}_ocr_backend",
            help="Unlimited-OCR ist die Empfehlung aus dem Feedback, braucht aber GPU/Server-Setup ausserhalb dieser Streamlit-App.",
        )
        if ocr_backend_label.startswith("Tesseract"):
            if pdf_loader.tesseract_available():
                st.caption("Tesseract lokal ist verfügbar.")
            else:
                st.warning("OCR ist vorbereitet, aber Tesseract ist lokal nicht verfügbar. Text-PDFs funktionieren weiterhin.")
        if ocr_backend_label.startswith("Baidu Unlimited-OCR"):
            if ocr_service.unlimited_ocr_available():
                st.success(f"Unlimited-OCR konfiguriert: {ocr_service.describe_backend('unlimited_ocr')}")
            else:
                st.info(
                    "Unlimited-OCR ist noch nicht konfiguriert. Setze UNLIMITED_OCR_BASE_URL "
                    "(OpenAI-kompatibler Endpoint) oder UNLIMITED_OCR_PATH (lokaler CLI-Befehl)."
                )
    ocr_provider = "unlimited_ocr" if ocr_backend_label.startswith("Baidu Unlimited-OCR") else "tesseract"
    return {
        "selected_names": selected_names,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "enable_ocr": enable_ocr,
        "ocr_provider": ocr_provider,
        "page_start": page_start,
        "page_end": page_end,
    }


def _render_page_range_inputs(
    key_prefix: str, pdfs: list[Path], selected_names: list[str]
) -> tuple[int | None, int | None]:
    """Let the user index the whole PDF or only a page range (large-PDF option)."""
    selected_paths = [pdf for pdf in pdfs if pdf.name in selected_names]
    max_pages = 0
    for pdf_path in selected_paths:
        try:
            max_pages = max(max_pages, pdf_loader.pdf_page_count(pdf_path))
        except (OSError, RuntimeError):
            continue

    st.markdown('<div class="index-step-label">2. Seitenumfang wählen</div>', unsafe_allow_html=True)
    if max_pages:
        st.caption(f"Größtes ausgewähltes PDF: {max_pages} Seiten.")
    if max_pages > LARGE_PDF_THRESHOLD:
        st.warning(
            f"Dieses PDF hat mehr als {LARGE_PDF_THRESHOLD} Seiten. "
            "Für bessere Performance kannst du nur ausgewählte Seiten indexieren."
        )

    mode = st.radio(
        "Seitenumfang",
        options=["Ganzes PDF analysieren", "Nur Seitenbereich analysieren"],
        index=1 if max_pages > LARGE_PDF_THRESHOLD else 0,
        key=f"{key_prefix}_page_range_mode",
        horizontal=True,
        label_visibility="collapsed",
    )
    if mode.startswith("Ganzes"):
        return None, None

    upper = max_pages or 10_000
    range_cols = st.columns(2)
    page_start = range_cols[0].number_input(
        "Startseite",
        min_value=1,
        max_value=upper,
        value=1,
        step=1,
        key=f"{key_prefix}_page_start",
    )
    default_end = min(20, upper)
    page_end = range_cols[1].number_input(
        "Endseite",
        min_value=1,
        max_value=upper,
        value=default_end,
        step=1,
        key=f"{key_prefix}_page_end",
    )
    if page_end < page_start:
        st.warning("Endseite liegt vor der Startseite. Es wird nur die Startseite indexiert.")
        page_end = page_start
    st.caption(f"Es werden nur die Seiten {int(page_start)}–{int(page_end)} extrahiert und indexiert.")
    return int(page_start), int(page_end)


def _render_scanned_pdf_hint(pdfs: list[Path], selected_names: list[str]) -> None:
    """Warn if a selected PDF looks scanned and therefore needs OCR."""
    for pdf_path in (pdf for pdf in pdfs if pdf.name in selected_names):
        try:
            if pdf_loader.is_scanned_pdf(pdf_path):
                st.warning(
                    f"„{pdf_path.name}“ scheint gescannt zu sein. OCR ist erforderlich, "
                    "um Text zu extrahieren. Aktiviere OCR unten."
                )
        except (OSError, RuntimeError):
            continue


def _default_selected_pdf_names(pdfs: list[Path]) -> list[str]:
    names = [pdf.name for pdf in pdfs]
    last_uploaded = [name for name in st.session_state.get("last_uploaded_pdfs", []) if name in names]
    return last_uploaded or names


def _short_filename(name: str, limit: int = 42) -> str:
    if len(name) <= limit:
        return name
    suffix = Path(name).suffix
    keep = max(12, limit - len(suffix) - 5)
    return f"{name[:keep]}...{suffix}"


def _render_index_summary(selected_names: list[str], chunk_size: int, overlap: int, enable_ocr: bool) -> None:
    st.markdown('<div class="index-step-label">4. Index bauen</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="index-summary">
            <div><span>Ausgewählt</span><strong>{len(selected_names)} PDFs</strong></div>
            <div><span>Backend</span><strong>{html.escape(rag_store.storage_backend())}</strong></div>
            <div><span>Chunk-Größe</span><strong>{chunk_size} Zeichen</strong></div>
            <div><span>Overlap</span><strong>{overlap} Zeichen</strong></div>
            <div><span>OCR</span><strong>{"aktiviert" if enable_ocr else "deaktiviert"}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _index_pdf_paths(
    selected_paths: list[Path],
    chunk_size: int,
    overlap: int,
    enable_ocr: bool,
    ocr_provider: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> None:
    total_pages = 0
    total_chunks = 0
    total_ocr_pages = 0
    backend = "n/a"
    indexed_files = []
    file_results = []
    start_time = time.perf_counter()
    for pdf_path in selected_paths:
        try:
            pages = pdf_loader.extract_pdf_pages(
                pdf_path,
                enable_ocr=enable_ocr,
                ocr_provider=ocr_provider,
                page_start=page_start,
                page_end=page_end,
            )
            chunks = chunking.chunk_pages(pages, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                st.warning(
                    f"{pdf_path.name}: Kein extrahierbarer Text gefunden. "
                    "Aktiviere OCR und installiere pytesseract/Pillow/Tesseract fuer gescannte PDFs."
                )
                continue
            result = rag_store.store_chunks(chunks)
        except (OSError, RuntimeError, ValueError) as exc:
            st.error(f"Indexierung fuer {pdf_path.name} fehlgeschlagen: {exc}")
            continue

        backend = result["backend"]
        total_pages += len(pages)
        total_chunks += len(chunks)
        ocr_pages = sum(1 for page in pages if str(page.get("extraction_method", "")).startswith("ocr_"))
        total_ocr_pages += ocr_pages
        indexed_files.append(pdf_path.name)
        file_results.append(
            {
                "pdf_name": pdf_path.name,
                "pages": len(pages),
                "chunks": len(chunks),
                "ocr_pages": ocr_pages,
                "backend": result["backend"],
            }
        )

    index_seconds = time.perf_counter() - start_time
    page_range_label = (
        f"{page_start}-{page_end}" if page_start or page_end else "ganzes PDF"
    )
    ocr_mode_label = (ocr_provider if enable_ocr else "disabled")
    embedding_model = embedding_config.active_model_label()
    st.session_state["index_stats"] = {
        "pdfs": indexed_files,
        "pages": total_pages,
        "chunks": total_chunks,
        "ocr_pages": total_ocr_pages,
        "backend": backend,
        "page_range": page_range_label,
        "embedding_model": embedding_model,
        "ocr_mode": ocr_mode_label,
        "index_seconds": index_seconds,
        "indexed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    if indexed_files:
        _log_scalability(
            event="index",
            pages=total_pages,
            chunks=total_chunks,
            seconds=index_seconds,
            detail=f"pdfs={len(indexed_files)};range={page_range_label};ocr={ocr_mode_label};embed={embedding_model}",
        )
    if indexed_files:
        _render_index_success_summary(
            indexed_files=len(indexed_files),
            pages=total_pages,
            chunks=total_chunks,
            ocr_pages=total_ocr_pages,
            backend=backend,
            file_results=file_results,
        )
    if not indexed_files:
        st.info("Es wurde kein PDF indexiert. Bitte pruefe, ob die PDF echten Text enthaelt.")


def _render_index_success_summary(
    indexed_files: int,
    pages: int,
    chunks: int,
    ocr_pages: int,
    backend: str,
    file_results: list[dict],
) -> None:
    st.markdown(
        f"""
        <div class="index-success">
            <div class="index-success-title">Index erfolgreich gebaut</div>
            <div class="index-success-grid">
                <div><span>Indexierte PDFs</span><strong>{indexed_files}</strong></div>
                <div><span>Seiten</span><strong>{pages}</strong></div>
                <div><span>Chunks</span><strong>{chunks}</strong></div>
                <div><span>OCR-Seiten</span><strong>{ocr_pages}</strong></div>
                <div><span>Backend</span><strong>{html.escape(backend)}</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Details pro PDF anzeigen", expanded=False):
        for file_result in file_results:
            st.markdown(
                f"""
                <div class="index-file-row">
                    <strong>{html.escape(str(file_result["pdf_name"]))}</strong>
                    <span>{file_result["pages"]} Seiten · {file_result["chunks"]} Chunks · {file_result["ocr_pages"]} OCR-Seiten · {html.escape(str(file_result["backend"]))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_question_controls(key_prefix: str, compact: bool, boxed: bool = True) -> None:
    if not rag_store.load_all_chunks():
        st.info("Erstelle zuerst den Index. Danach kannst du hier deine Frage an den PDF-Volltext eingeben.")
        return

    if boxed:
        with st.container(border=True):
            question, top_k, selected_sections, neighbor_radius = _render_question_inputs(key_prefix, compact)
    else:
        question, top_k, selected_sections, neighbor_radius = _render_question_inputs(key_prefix, compact)

    if st.button("Antwort mit Quellen generieren", type="primary", key=f"{key_prefix}_ask_button"):
        if not question.strip():
            st.warning("Gib zuerst eine Frage ein.")
            return

        retrieval_start = time.perf_counter()
        chunks = rag_retriever.search_relevant_chunks(
            question, top_k=top_k, sections=selected_sections, neighbor_radius=neighbor_radius
        )
        retrieval_seconds = time.perf_counter() - retrieval_start
        answer_result = rag_answer.generate_answer(question, chunks)
        st.session_state["pdf_question"] = question
        st.session_state["selected_sections"] = selected_sections
        st.session_state["retrieved_chunks"] = chunks
        st.session_state["retrieval_seconds"] = retrieval_seconds
        st.session_state["pdf_answer"] = _prepare_answer_for_display(answer_result["answer"], chunks)
        st.session_state["answer_mode"] = answer_result["mode"]
        _save_current_history(question)
        _log_scalability(
            event="retrieval",
            pages=0,
            chunks=len(chunks),
            seconds=retrieval_seconds,
            detail=f"top_k={top_k};neighbors={neighbor_radius}",
        )


def _render_question_inputs(key_prefix: str, compact: bool) -> tuple[str, int, list[str], int]:
    st.markdown("#### Frage an den PDF-Volltext")
    st.caption("Die Antwort darf nur auf den indexierten PDF-Quellen basieren und zeigt Seitenreferenzen.")
    st.markdown('<div class="index-step-label">1. Fragetyp wählen</div>', unsafe_allow_html=True)
    preset = _render_question_type_buttons(key_prefix)
    default_questions = {
        "Kernaussagen": "Was sind die Kernaussagen des gesamten Papers? Fasse die zentrale These, Methode, wichtigste Ergebnisse und Limitationen zusammen.",
        "Details": "Welche konkreten Sicherheitsrisiken und Gegenmassnahmen werden im Dokument genannt?",
        "Eigene Frage": st.session_state.get("pdf_question", "Welche Sicherheitsrisiken werden im Dokument genannt?"),
    }
    st.markdown('<div class="index-step-label">2. Frage eingeben</div>', unsafe_allow_html=True)
    question = st.text_area(
        "Deine Frage",
        value=st.session_state.get("pdf_question", default_questions[preset]),
        height=140,
        key=f"{key_prefix}_question",
        label_visibility="collapsed",
    )
    retrieval_cols = st.columns(2)
    top_k = retrieval_cols[0].slider(
        "Top-K Quellen",
        min_value=3,
        max_value=15,
        value=5,
        key=f"{key_prefix}_top_k",
        help="Anzahl der relevantesten Chunks, die abgerufen werden. Standard: 5.",
    )
    expansion_label = retrieval_cols[1].selectbox(
        "Kontext-Erweiterung",
        options=[
            "Keine Erweiterung",
            "1 Nachbar-Chunk einbeziehen",
            "2 Nachbar-Chunks einbeziehen",
        ],
        index=1,
        key=f"{key_prefix}_context_expansion",
        help="Fügt angrenzende Chunks derselben Seite hinzu, z. B. p60-c0/p60-c2 um p60-c1.",
    )
    neighbor_radius = 0 if expansion_label.startswith("Keine") else (1 if expansion_label.startswith("1") else 2)
    section_options = _indexed_sections()
    selected_sections: list[str] = []
    if section_options:
        st.markdown(
            '<div class="section-help section-help-primary">Optional: Sektionen für die Analyse auswählen. Unbekannt = Abschnitt konnte nicht sicher erkannt werden.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-help">Sektionen für die Analyse. Unbekannt = Abschnitt konnte nicht sicher erkannt werden.</div>',
            unsafe_allow_html=True,
        )
        selected_sections = st.multiselect(
            "3. Sektionen optional auswählen",
            options=section_options,
            default=_default_selected_sections(section_options),
            key=f"{key_prefix}_sections",
            help="Begrenzt die Antwort auf bestimmte Paper-Sektionen, z. B. Methods, Results oder Limitations.",
        )
    st.markdown('<div class="index-step-label">4. Antwort generieren</div>', unsafe_allow_html=True)
    st.caption("Mehrere Chunks werden gemeinsam als Kontext genutzt, damit die Antwort Kernaussagen statt nur Einzelsaetze abdeckt.")
    return question, top_k, selected_sections, neighbor_radius


def _render_question_type_buttons(key_prefix: str) -> str:
    key = f"{key_prefix}_question_type_choice"
    options = ["Kernaussagen", "Details", "Eigene Frage"]
    selected = st.pills(
        "Fragetyp",
        options,
        default="Kernaussagen",
        key=key,
        label_visibility="collapsed",
    )
    return selected or "Kernaussagen"


def _indexed_sections() -> list[str]:
    sections = {
        str(entry.get("metadata", {}).get("section", "Unbekannt"))
        for entry in rag_store.load_all_chunks()
        if entry.get("metadata", {}).get("section")
    }
    return sorted(sections)


def _default_selected_sections(section_options: list[str]) -> list[str]:
    preferred = {
        "Abstract",
        "Introduction",
        "Methods",
        "Results",
        "Discussion",
        "Conclusion",
        "Limitations",
        "Unbekannt",
    }
    selected = [section for section in section_options if section in preferred]
    return selected or [section for section in section_options if section != "References"] or section_options


def _render_sources_preview(expanded_first: bool = False) -> None:
    chunks = st.session_state.get("retrieved_chunks", [])
    if not chunks:
        return
    st.markdown("### Gefundene Quellen")
    retrieval_seconds = st.session_state.get("retrieval_seconds")
    context_count = sum(1 for chunk in chunks if chunk.get("is_context"))
    meta_bits = [f"{len(chunks)} Chunks"]
    if context_count:
        meta_bits.append(f"davon {context_count} Kontext-Nachbarn")
    if isinstance(retrieval_seconds, (int, float)):
        meta_bits.append(f"Retrieval-Zeit: {retrieval_seconds:.3f}s")
    st.caption(" · ".join(meta_bits))
    for index, chunk in enumerate(chunks, start=1):
        source_title = _source_title(index, chunk)
        excerpt = _chunk_excerpt(chunk.get("text", ""))
        score = _format_source_score(chunk) or "n/a"
        with st.expander(
            source_title,
            expanded=expanded_first and index == 1,
        ):
            st.markdown(
                f"""
                <div class="source-card">
                    <div class="source-card-title">{html.escape(source_title)}</div>
                    <div class="source-meta-grid">
                        <div><span>PDF</span><strong>{html.escape(str(chunk.get("pdf_name", "unknown.pdf")))}</strong></div>
                        <div><span>Seite</span><strong>{html.escape(str(chunk.get("page_number", "n/a")))}</strong></div>
                        <div><span>Chunk</span><strong>{html.escape(str(chunk.get("chunk_id", "n/a")))}</strong></div>
                        <div><span>Sektion</span><strong>{html.escape(str(chunk.get("section", "Unbekannt")))}</strong></div>
                        <div><span>Extraktion</span><strong>{html.escape(str(chunk.get("extraction_method", "pdf_text")))}</strong></div>
                    </div>
                    <div class="source-meta-extra">
                        <span>Retrieval Score</span><strong>{html.escape(score)}</strong>
                    </div>
                    <div class="source-excerpt"><strong>Auszug:</strong> {html.escape(excerpt)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Kompletten Originaltext aus dem PDF anzeigen", expanded=False):
                st.text_area(
                    "Vollstaendiger Chunk",
                    value=_clean_source_text(chunk.get("text", "")),
                    height=250,
                    key=f"full_chunk_{index}_{chunk.get('chunk_id', 'unknown')}",
                    label_visibility="collapsed",
                    disabled=True,
                )


def _chunk_excerpt(text: str, limit: int = 650) -> str:
    clean_text = _start_at_sentence_boundary(_clean_source_text(text))
    if len(clean_text) <= limit:
        return clean_text
    return clean_text[:limit].rsplit(" ", 1)[0] + "..."


def _source_title(index: int, chunk: dict) -> str:
    context_note = " (Kontext)" if chunk.get("is_context") else ""
    return (
        f"Quelle {index} – Seite {chunk.get('page_number', 'n/a')} – "
        f"Chunk {chunk.get('chunk_id', 'n/a')}{context_note}"
    )


def _source_score_value(chunk: dict) -> float | None:
    score = chunk.get("retrieval_score", chunk.get("score"))
    if isinstance(score, (int, float)):
        numeric_score = float(score)
        if numeric_score > 0:
            return numeric_score
    return None


def _format_source_score(chunk: dict) -> str:
    score = _source_score_value(chunk)
    if score is None:
        return ""
    return f"{score:.2f}"


def _clean_incomplete_markdown(answer: str) -> str:
    clean_answer = (answer or "").strip()
    clean_answer = re.sub(r"\n?\s*\*\*[A-Za-zÄÖÜäöüß]{0,24}\s*$", "", clean_answer).rstrip()
    if clean_answer.count("**") % 2:
        clean_answer = re.sub(r"\s*\*\*[^*\n]{0,80}$", "", clean_answer).rstrip()
    return clean_answer


def _prepare_answer_for_display(answer: str, chunks: list[dict]) -> str:
    clean_answer = _clean_incomplete_markdown(answer)
    return _normalize_answer_source_references(clean_answer, chunks)


def _normalize_answer_source_references(answer: str, chunks: list[dict]) -> str:
    pdf_pages = {
        str(chunk.get("pdf_name", "")): str(chunk.get("page_number", "n/a"))
        for chunk in chunks
        if chunk.get("pdf_name")
    }
    source_pages = {
        str(index): (
            str(chunk.get("pdf_name", "unknown.pdf")),
            str(chunk.get("page_number", "n/a")),
        )
        for index, chunk in enumerate(chunks, start=1)
    }

    def normalize_reference(match: re.Match) -> str:
        content = match.group(1).strip()
        content = re.sub(r",?\s*page\s+(\d+)", r", Seite \1", content, flags=re.IGNORECASE)
        if re.search(r"\bseite\s+\d+", content, flags=re.IGNORECASE):
            return f"[{content}]"
        source_match = re.fullmatch(r"(?:source|quelle)\s+(\d+)", content, flags=re.IGNORECASE)
        if source_match:
            pdf_name, page_number = source_pages.get(source_match.group(1), ("", ""))
            if pdf_name and page_number.isdigit():
                return f"[{pdf_name}, Seite {page_number}]"
        for pdf_name, page_number in pdf_pages.items():
            if pdf_name and pdf_name in content and str(page_number).isdigit():
                return f"[{content}, Seite {page_number}]"
        return f"[{content}]"

    return re.sub(r"\[([^\]]+)\]", normalize_reference, answer)


def _clean_source_text(text: str) -> str:
    clean_text = html.unescape(str(text or ""))
    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
    return " ".join(clean_text.split())


def _build_short_answer(question: str, answer: str, chunks: list[dict]) -> str:
    highlighted_terms = _extract_highlighted_terms(question, chunks)
    if highlighted_terms:
        return "\n".join(f"- {term}" for term in highlighted_terms[:4])

    bullets = []
    for line in answer.splitlines():
        clean_line = line.strip(" -0123456789.")
        if not clean_line:
            continue
        if clean_line.lower().startswith(
            (
                "frage:",
                "**frage:**",
                "hinweis:",
                "auf basis der gefundenen",
                "references:",
                "spezifische rag",
                "ergänzende",
                "ergaenzende",
            )
        ):
            continue
        clean_line = clean_line.split("[", 1)[0].strip()
        clean_line = _start_at_sentence_boundary(clean_line)
        if clean_line:
            bullets.append(_short_text(clean_line, limit=220))
        if len(bullets) >= 4:
            break

    if bullets:
        return "\n".join(f"- {bullet}" for bullet in bullets[:4])

    return ""


def _extract_highlighted_terms(question: str, chunks: list[dict]) -> list[str]:
    lower_question = question.lower()
    if not any(term in lower_question for term in ("risiko", "risk", "security", "sicherheit", "rag")):
        return []

    text = " ".join(str(chunk.get("text", "")).lower() for chunk in chunks)
    candidates = [
        ("RAG-Datenvergiftung", ("rag poisoning", "data poisoning", "datenvergiftung")),
        ("SQL-Injection", ("sql injection", "sql-injection")),
        ("unautorisierte Datenexposition", ("unauthorized data exposure", "unauthorised data exposure", "data exposure")),
        ("Code-Injection", ("code injection", "code-injection")),
        ("Prompt-Injection", ("prompt injection", "prompt-injection")),
        ("Tool-Missbrauch", ("tool misuse", "tool abuse")),
        ("Zugriffskontrollen fuer Vector Databases", ("access control", "access controls", "vector database", "vector databases")),
        ("Post-Retrieval Filtering", ("post-retrieval filtering", "retrieval filtering")),
        ("Content Verification vor Embedding", ("content verification", "before embedding")),
        ("Rate-Limiting", ("rate-limiting", "rate limiting")),
    ]
    return [label for label, phrases in candidates if any(phrase in text for phrase in phrases)][:6]


def _start_at_sentence_boundary(text: str) -> str:
    if not text:
        return text
    clean_text = text.lstrip(" .,:;)-]")
    if len(clean_text) < 40:
        return clean_text
    for marker in (". ", "? ", "! "):
        position = clean_text.find(marker)
        if 0 <= position <= 180 and position + len(marker) < len(clean_text):
            candidate = clean_text[position + len(marker):].lstrip()
            if candidate:
                return candidate
    return clean_text


def _render_memory() -> None:
    st.subheader("Memory")
    st.write(
        "Frühere Research Runs werden gespeichert, damit du vergangene Recherchen "
        "wiederfinden und durchsuchen kannst."
    )
    st.caption(f"Active storage: {_relative_backend_label(memory.memory_backend())}")
    recall_query = st.text_input(
        "Memory durchsuchen",
        value=st.session_state.get("research_query", pipeline.DEFAULT_QUERY),
        key="memory_recall_query",
    )
    if not st.button("Fruehere Recherchen abrufen", type="primary", key="memory_recall_button"):
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
    review = st.session_state.get("review")
    if not answer and review is None:
        st.info("Starte zuerst die Paper-Suche oder stelle eine PDF-Frage. Danach ist der Export verfuegbar.")
        return

    markdown = _build_export_markdown(question, answer, chunks, review)
    _render_export_summary(review, answer, chunks)

    if st.button("Markdown Export schreiben", type="primary", key="export_write_md_button"):
        EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXPORT_PATH.write_text(markdown, encoding="utf-8")
        st.success(f"Export geschrieben: {EXPORT_PATH.relative_to(PROJECT_DIR).as_posix()}")

    st.download_button(
        "Markdown herunterladen",
        data=markdown,
        file_name="pdf_rag_answer.md",
        mime="text/markdown",
        use_container_width=True,
        key="download_md_button",
    )

    with st.expander("Preview Markdown anzeigen", expanded=False):
        st.code(markdown, language="markdown")

    _render_source_table_exports(question, answer, chunks)


def _render_source_table_exports(question: str, answer: str, chunks: list[dict]) -> None:
    """CSV and Excel export of the retrieved sources with full context fields."""
    st.markdown("#### Quellen als Tabelle exportieren (CSV / Excel)")
    if not chunks:
        st.info("Stelle zuerst eine PDF-Frage. Danach sind CSV- und Excel-Export der Quellen verfügbar.")
        return

    stats = st.session_state.get("index_stats", {})
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = export_utils.build_rows(
        question=question,
        answer=_prepare_answer_for_display(answer, chunks),
        chunks=chunks,
        timestamp=timestamp,
        embedding_model=embedding_config.active_model_label(),
        ocr_mode=str(stats.get("ocr_mode", ocr_service.get_ocr_mode())),
        page_range=str(stats.get("page_range", "ganzes PDF")),
    )

    csv_text = export_utils.to_csv(rows)
    csv_col, xlsx_col = st.columns(2)
    if csv_col.button("CSV Export schreiben", key="export_write_csv_button"):
        CSV_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CSV_EXPORT_PATH.write_text(csv_text, encoding="utf-8")
        st.success(f"CSV geschrieben: {CSV_EXPORT_PATH.relative_to(PROJECT_DIR).as_posix()}")
    csv_col.download_button(
        "CSV herunterladen",
        data=csv_text,
        file_name="sources.csv",
        mime="text/csv",
        use_container_width=True,
        key="download_csv_button",
    )

    excel_bytes = export_utils.to_excel(rows)
    if excel_bytes is None:
        xlsx_col.info("Excel-Export benötigt das Paket openpyxl (in requirements.txt enthalten).")
    else:
        if xlsx_col.button("Excel Export schreiben", key="export_write_xlsx_button"):
            XLSX_EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            XLSX_EXPORT_PATH.write_bytes(excel_bytes)
            st.success(f"Excel geschrieben: {XLSX_EXPORT_PATH.relative_to(PROJECT_DIR).as_posix()}")
        xlsx_col.download_button(
            "Excel herunterladen",
            data=excel_bytes,
            file_name="sources.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_xlsx_button",
        )


def _render_export_summary(review, answer: str, chunks: list[dict]) -> None:
    status = "bereit" if review or answer else "noch nicht bereit"
    discovery_status = "Verfügbar" if review else "Nicht verfügbar"
    ranking_status = "Verfügbar" if review else "Nicht verfügbar"
    if answer and review is None:
        discovery_status = "In diesem Workflow nicht verwendet"
        ranking_status = "In diesem Workflow nicht verwendet"
    items = [
        ("Exportstatus", status),
        ("Format", "Markdown"),
        ("Paper Discovery Results", discovery_status),
        ("Ranking", ranking_status),
        ("PDF-RAG Antwort", "Verfügbar" if answer else "Nicht verfügbar"),
        ("Quellen mit Seitenangaben", "Verfügbar" if chunks else "Nicht verfügbar"),
    ]
    st.markdown("#### Export-Übersicht")
    for label, value in items:
        st.markdown(f"- **{label}:** {value}")


def _build_export_markdown(
    question: str,
    answer: str,
    chunks: list[dict],
    review=None,
) -> str:
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    answer = _prepare_answer_for_display(answer, chunks)
    has_source_scores = any(_source_score_value(chunk) is not None for chunk in chunks)
    lines = [
        "# Research Paper Discovery Agent",
        "",
        "## Export Info",
        "",
        f"- Exported at: {exported_at}",
        f"- Antwortmodus: {st.session_state.get('answer_mode', 'unknown')}",
        f"- Ausgewaehlte Sektionen: {', '.join(st.session_state.get('selected_sections', [])) or 'Alle'}",
        f"- Embedding model: {embedding_config.active_model_label()}",
        "",
    ]

    if review is not None:
        lines.extend(
            [
                "## Paper Discovery Result",
                "",
                "### Query",
                "",
                review.query,
                "",
                "### Top Ranked Papers",
                "",
                "| Rank | Title | Year | Score | Source |",
                "|------|-------|------|-------|--------|",
            ]
        )
        for rank, paper in enumerate(review.papers, start=1):
            lines.append(
                "| "
                f"{rank} | {_md_cell(paper.title or 'No title available')} | "
                f"{paper.year or 'n/a'} | {paper.relevance_score} | "
                f"{_md_cell(paper.source or 'n/a')} |"
            )
        lines.extend(
            [
                "",
                "## PDF-RAG Result",
                "",
            ]
        )
    else:
        lines.extend(["## PDF-RAG Result", ""])

    if not answer:
        return "\n".join(lines)

    lines.extend(
        [
            "## Frage",
            "",
            question,
            "",
            "## Kurzantwort",
            "",
            _build_short_answer(question, answer, chunks),
            "",
            "## Details",
            "",
            answer,
            "",
            "## Quellen",
            "",
        ]
    )
    if has_source_scores:
        lines.extend(
            [
                "| Nr. | PDF | Seite | Chunk ID | Sektion | Extraktion | Score |",
                "|-----|-----|-------|----------|---------|------------|-------|",
            ]
        )
    else:
        lines.extend(
            [
                "| Nr. | PDF | Seite | Chunk ID | Sektion | Extraktion |",
                "|-----|-----|-------|----------|---------|------------|",
            ]
        )
    for index, chunk in enumerate(chunks, start=1):
        row = (
            "| "
            f"{index} | {_md_cell(str(chunk.get('pdf_name', 'unknown.pdf')))} | "
            f"{chunk.get('page_number', 'n/a')} | "
            f"{_md_cell(str(chunk.get('chunk_id', 'n/a')))} | "
            f"{_md_cell(str(chunk.get('section', 'Unbekannt')))} | "
            f"{_md_cell(str(chunk.get('extraction_method', 'pdf_text')))} |"
        )
        if has_source_scores:
            row = row[:-1] + f" {_format_source_score(chunk)} |"
        lines.append(row)
    lines.append("")
    lines.extend(["## Quellenauszuege", ""])
    for index, chunk in enumerate(chunks, start=1):
        score = _format_source_score(chunk)
        source_meta = [
            f"- PDF name: {chunk.get('pdf_name', 'unknown.pdf')}",
            f"- Page number: {chunk.get('page_number', 'n/a')}",
            f"- Chunk ID: {chunk.get('chunk_id', 'n/a')}",
            f"- Section: {chunk.get('section', 'Unbekannt')}",
            f"- Extraction method: {chunk.get('extraction_method', 'pdf_text')}",
        ]
        if score:
            source_meta.append(f"- Score: {score}")
        source_meta.append(f"- Timestamp: {exported_at}")
        lines.extend(
            [
                f"### Quelle {index}",
                "",
                *source_meta,
                "",
                f"Excerpt: {_chunk_excerpt(chunk.get('text', ''), limit=650)}",
                "",
            ]
        )
    if review is not None:
        lines.extend(["## Detailed Paper Notes", ""])
        summaries_by_id = {summary.paper_id: summary for summary in review.summaries}
        for rank, paper in enumerate(review.papers, start=1):
            summary = summaries_by_id.get(paper.id)
            lines.extend(
                [
                    f"### {rank}. {paper.title or 'No title available'}",
                    "",
                    f"- Score: {paper.relevance_score}",
                    f"- Year: {paper.year or 'n/a'}",
                    f"- Source: {paper.source or 'n/a'}",
                    f"- URL: {paper.url or 'n/a'}",
                    "",
                    f"**Abstract excerpt:** {_short_text(paper.abstract or 'No abstract available.', limit=700)}",
                    "",
                ]
            )
            if summary:
                lines.extend(
                    [
                        f"**Summary:** {_short_text(summary.contribution, limit=450)}",
                        "",
                    ]
                )
    return "\n".join(lines)


def _md_cell(value: str) -> str:
    return " ".join(str(value).replace("|", "\\|").split())


def _relative_backend_label(label: str) -> str:
    return label.replace(str(PROJECT_DIR), "").replace("\\", "/").replace("(/", "(")


def _source_label(review) -> str:
    sources = {paper.source for paper in review.papers}
    if "arXiv live" in sources:
        return "arXiv live"
    if "Semantic Scholar live" in sources:
        return "Semantic Scholar"
    if any("cached" in (source or "").lower() for source in sources):
        return "Cache"
    return "Fallback"


def _display_source_label(source: str | None) -> str:
    clean_source = source or "n/a"
    lower_source = clean_source.lower()
    if "fallback" in lower_source:
        return "Offline-Fallback"
    if "cached" in lower_source:
        return "Cache"
    return clean_source


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
    display_name = _short_filename(pdf_path.name, limit=54)
    st.markdown(
        f"""
        <div class="file-card" title="{html.escape(pdf_path.name)}">
            <strong>{html.escape(display_name)}</strong><br>
            Größe: {size_kb:.1f} KB<br>
            Status: {html.escape(status)}<br>
            <span>Hinweis: Diese Datei kann im nächsten Schritt für den Index ausgewählt werden.</span>
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


def _log_scalability(event: str, pages: int, chunks: int, seconds: float, detail: str = "") -> None:
    """Append a simple scalability record (pages, chunks, timing) to a CSV log."""
    try:
        SCALABILITY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        new_file = not SCALABILITY_LOG_PATH.exists()
        with SCALABILITY_LOG_PATH.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new_file:
                writer.writerow(["timestamp", "event", "pages", "chunks", "seconds", "detail"])
            writer.writerow(
                [
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                    event,
                    pages,
                    chunks,
                    f"{seconds:.4f}",
                    detail,
                ]
            )
    except OSError:
        pass


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

            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid #d8e2eb;
                border-radius: 8px;
                padding: 12px 14px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.05);
            }

            div[data-testid="stMetric"] label,
            div[data-testid="stMetric"] label p {
                color: #344054 !important;
                font-weight: 800 !important;
            }

            div[data-testid="stMetricValue"],
            div[data-testid="stMetricValue"] div {
                color: #101820 !important;
                font-weight: 850 !important;
            }

            details[data-testid="stExpander"] {
                border-color: #cbd8e4 !important;
                border-radius: 8px !important;
            }

            div[data-testid="stExpander"] details,
            div[data-testid="stExpander"] {
                border-color: #cbd8e4 !important;
                border-radius: 8px !important;
            }

            details[data-testid="stExpander"] > summary {
                background: #f7fafc !important;
                border-radius: 8px 8px 0 0 !important;
            }

            div[data-testid="stExpander"] summary,
            div[data-testid="stExpander"] button {
                background: #f7fafc !important;
                border-radius: 8px 8px 0 0 !important;
            }

            details[data-testid="stExpander"] > summary,
            details[data-testid="stExpander"] > summary * {
                color: #101820 !important;
                font-weight: 800 !important;
            }

            div[data-testid="stExpander"] summary,
            div[data-testid="stExpander"] summary *,
            div[data-testid="stExpander"] button,
            div[data-testid="stExpander"] button * {
                color: #101820 !important;
                font-weight: 800 !important;
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

            div[data-baseweb="textarea"] textarea:disabled {
                -webkit-text-fill-color: #101820 !important;
                background: #ffffff !important;
                color: #101820 !important;
                opacity: 1 !important;
                white-space: pre-wrap !important;
                word-break: break-word !important;
            }

            div[data-baseweb="textarea"] textarea::placeholder,
            div[data-baseweb="input"] input::placeholder {
                color: #667085;
            }

            label,
            label *,
            div[data-testid="stMarkdownContainer"] p,
            div[data-testid="stCaptionContainer"],
            div[data-testid="stCaptionContainer"] * {
                color: #344054 !important;
            }

            div[data-baseweb="select"] > div,
            div[data-baseweb="select"] input,
            div[data-baseweb="select"] span {
                background: #ffffff !important;
                color: #101820 !important;
            }

            div[data-baseweb="select"] > div {
                border-color: #b9c8d6 !important;
                border-radius: 8px !important;
                min-height: 44px !important;
            }

            div[data-baseweb="select"] svg {
                color: #101820 !important;
                fill: #101820 !important;
            }

            div[data-baseweb="tag"] {
                background: #ef5b5b !important;
                border-radius: 6px !important;
                color: #ffffff !important;
                max-width: 100% !important;
            }

            div[data-baseweb="tag"] span,
            div[data-baseweb="tag"] svg {
                color: #ffffff !important;
                fill: #ffffff !important;
            }

            div[data-baseweb="tag"] span {
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                white-space: nowrap !important;
            }

            div[data-testid="stSegmentedControl"] {
                background: #ffffff !important;
                border: 1px solid #cfd9e3 !important;
                border-radius: 8px !important;
                padding: 4px !important;
            }

            div[data-testid="stSegmentedControl"] div,
            div[data-testid="stSegmentedControl"] label,
            div[data-testid="stSegmentedControl"] [role="radiogroup"] {
                background: #ffffff !important;
                color: #101820 !important;
            }

            div[data-testid="stSegmentedControl"] button {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 6px !important;
                color: #111827 !important;
                font-weight: 850 !important;
                min-height: 40px !important;
            }

            div[data-testid="stSegmentedControl"] button:hover {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] button[aria-selected="true"],
            div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] [role="radio"],
            div[data-testid="stSegmentedControl"] [role="option"] {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 6px !important;
                color: #111827 !important;
                font-weight: 850 !important;
            }

            div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
            div[data-testid="stSegmentedControl"] [role="option"][aria-selected="true"] {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] [role="radio"]:hover,
            div[data-testid="stSegmentedControl"] [role="option"]:hover {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] button *,
            div[data-testid="stSegmentedControl"] button[aria-pressed="true"] *,
            div[data-testid="stSegmentedControl"] button[aria-selected="true"] *,
            div[data-testid="stSegmentedControl"] button[aria-checked="true"] *,
            div[data-testid="stSegmentedControl"] [role="radio"] *,
            div[data-testid="stSegmentedControl"] [role="option"] * {
                color: inherit !important;
            }

            div[data-testid="stToggle"] label,
            div[data-testid="stToggle"] label * {
                color: #101820 !important;
                font-weight: 800 !important;
            }

            div[data-testid="stToggle"] {
                background: #ffffff !important;
                border: 2px solid #cfd9e3 !important;
                border-radius: 8px !important;
                margin: 10px 0 6px !important;
                padding: 14px 16px !important;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.05) !important;
            }

            div[data-testid="stToggle"] [role="switch"] {
                background: #98a2b3 !important;
                border: 2px solid #475467 !important;
                border-radius: 999px !important;
                box-shadow: 0 0 0 3px rgba(16, 24, 32, 0.08) !important;
                min-height: 28px !important;
                min-width: 54px !important;
            }

            div[data-testid="stToggle"] [role="switch"][aria-checked="true"] {
                background: #2e9f63 !important;
                border-color: #247a49 !important;
                box-shadow: 0 0 0 3px rgba(46, 159, 99, 0.18) !important;
            }

            div[data-testid="stToggle"] [role="switch"] * {
                opacity: 1 !important;
            }

            div[data-testid="stToggle"] input + div {
                opacity: 1 !important;
            }

            div[data-testid="stToggle"] input:not(:checked) + div {
                background: #98a2b3 !important;
                border-color: #475467 !important;
            }

            div[data-testid="stToggle"] input:checked + div {
                background: #2e9f63 !important;
                border-color: #247a49 !important;
            }

            div[data-testid="stTabs"] button[role="tab"] {
                background: #ffffff !important;
                border: 1px solid #cfd9e3 !important;
                border-radius: 8px 8px 0 0 !important;
                color: #101820 !important;
                font-weight: 850 !important;
                margin-right: 6px !important;
                padding: 10px 14px !important;
            }

            div[data-testid="stTabs"] button[role="tab"] * {
                color: #101820 !important;
            }

            div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
                background: #fff5f5 !important;
                border-color: #ef5b5b !important;
                border-bottom-color: #fff5f5 !important;
                color: #b42318 !important;
            }

            div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] * {
                color: #b42318 !important;
            }

            div[data-testid="stTabs"] button[role="tab"]:hover {
                background: #f7fafc !important;
                border-color: #ef5b5b !important;
                color: #101820 !important;
            }

            div[data-baseweb="popover"],
            div[data-baseweb="popover"] *,
            ul[role="listbox"],
            ul[role="listbox"] * {
                background: #ffffff !important;
                color: #101820 !important;
            }

            li[role="option"] {
                background: #ffffff !important;
                color: #101820 !important;
            }

            li[role="option"]:hover,
            li[aria-selected="true"] {
                background: #fff5f5 !important;
                color: #b42318 !important;
            }

            .stButton > button:disabled,
            button:disabled {
                background: #e4e7ec !important;
                border: 1px solid #cbd5e1 !important;
                color: #667085 !important;
                opacity: 1 !important;
            }

            .stLinkButton a,
            div[data-testid="stLinkButton"] a {
                background: #ef5b5b !important;
                border: 1px solid #ef5b5b !important;
                color: #ffffff !important;
                font-weight: 850 !important;
            }

            .stLinkButton a *,
            div[data-testid="stLinkButton"] a * {
                color: #ffffff !important;
            }

            .disabled-link-button {
                align-items: center;
                background: #e4e7ec;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                color: #667085;
                display: inline-flex;
                font-weight: 850;
                min-height: 38px;
                padding: 0 14px;
            }

            div[data-testid="stFileUploaderDropzone"] {
                background: #ffffff !important;
                border: 2px dashed #9fb2c3 !important;
                border-radius: 8px !important;
                min-height: 124px;
            }

            div[data-testid="stFileUploaderDropzone"] * {
                color: #101820 !important;
            }

            .upload-hint {
                background: #f7fafc;
                border: 1px solid #d8e2eb;
                border-radius: 8px;
                color: #344054;
                display: inline-flex;
                font-size: 0.9rem;
                font-weight: 750;
                margin: 4px 0 10px;
                padding: 7px 10px;
            }

            .upload-cta {
                align-items: flex-start;
                background: #ffffff;
                border: 2px dashed #9fb2c3;
                border-radius: 8px;
                color: #101820;
                display: grid;
                gap: 6px;
                margin: 8px 0 12px;
                padding: 18px 20px;
            }

            .upload-cta strong {
                color: #101820;
                font-size: 1.05rem;
                font-weight: 850;
            }

            .upload-cta span {
                color: #475467;
                font-size: 0.92rem;
                font-weight: 750;
            }

            div[data-testid="stFileUploader"] button {
                background: #ef5b5b !important;
                border: 1px solid #ef5b5b !important;
                color: #ffffff !important;
                font-weight: 850 !important;
            }

            div[data-testid="stFileUploader"] button * {
                color: #ffffff !important;
            }

            .upload-success {
                background: #edf9f2;
                border: 1px solid #b9e4c9;
                border-left: 6px solid #2e9f63;
                border-radius: 8px;
                color: #101820;
                display: grid;
                gap: 4px;
                margin: 10px 0;
                padding: 13px 15px;
            }

            .upload-success strong {
                color: #14532d;
                font-weight: 850;
            }

            .upload-success span {
                color: #344054;
                overflow-wrap: anywhere;
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

            .status-box span {
                color: #344054;
                display: block;
                line-height: 1.45;
                margin-top: 6px;
            }

            .ocr-panel,
            .index-success {
                background: #ffffff;
                border: 1px solid #cbd8e4;
                border-left: 6px solid #ef5b5b;
                border-radius: 8px;
                color: #101820;
                margin: 14px 0 10px;
                padding: 15px 17px;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.05);
            }

            .ocr-panel {
                border: 2px solid #cbd8e4;
                border-left: 8px solid #ef5b5b;
                box-shadow: 0 6px 16px rgba(16, 24, 32, 0.08);
            }

            .ocr-panel-title,
            .index-success-title {
                color: #101820;
                font-size: 1rem;
                font-weight: 850;
                line-height: 1.3;
            }

            .ocr-panel-copy {
                color: #344054;
                line-height: 1.45;
                margin-top: 6px;
            }

            .ocr-panel-note {
                background: #f7fafc;
                border: 1px solid #d8e2eb;
                border-radius: 8px;
                color: #344054;
                font-size: 0.92rem;
                font-weight: 750;
                line-height: 1.45;
                margin: 8px 0 4px;
                padding: 10px 12px;
            }

            .ocr-status {
                border-radius: 999px;
                display: inline-flex;
                font-size: 0.84rem;
                font-weight: 850;
                margin: 8px 0 12px;
                padding: 7px 11px;
                text-transform: uppercase;
            }

            .toggle-status {
                border-radius: 999px;
                display: inline-flex;
                font-size: 0.84rem;
                font-weight: 850;
                line-height: 1.2;
                margin: 8px 0 12px;
                padding: 8px 12px;
                text-transform: uppercase;
            }

            .toggle-on {
                background: #edf9f2;
                border: 1px solid #b9e4c9;
                color: #247a49;
            }

            .toggle-off {
                background: #f1f5f9;
                border: 1px solid #cfd9e3;
                color: #344054;
            }

            .ocr-on {
                background: #edf9f2;
                border: 1px solid #b9e4c9;
                color: #247a49;
            }

            .ocr-off {
                background: #f1f5f9;
                border: 1px solid #cfd9e3;
                color: #344054;
            }

            .index-success {
                border-left-color: #2e9f63;
            }

            .index-success-grid {
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                margin-top: 12px;
            }

            .index-summary {
                background: #ffffff;
                border: 1px solid #cbd8e4;
                border-radius: 8px;
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(5, minmax(0, 1fr));
                margin: 12px 0 14px;
                padding: 12px;
            }

            .index-success-grid div,
            .index-summary div {
                background: #f7fafc;
                border: 1px solid #dde7ef;
                border-radius: 6px;
                padding: 9px 10px;
            }

            .index-success-grid span,
            .index-summary span,
            .source-meta-extra span {
                color: #667085;
                display: block;
                font-size: 0.72rem;
                font-weight: 800;
                margin-bottom: 5px;
                text-transform: uppercase;
            }

            .index-success-grid strong,
            .index-summary strong,
            .source-meta-extra strong {
                color: #101820;
                display: block;
                font-weight: 850;
                overflow-wrap: anywhere;
            }

            .section-help {
                background: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 8px;
                color: #7c2d12;
                font-size: 0.9rem;
                line-height: 1.45;
                margin: 12px 0 8px;
                padding: 10px 12px;
            }

            .section-help:not(.section-help-primary) {
                display: none;
            }

            .question-type-pill {
                align-items: center;
                border-radius: 999px;
                display: flex;
                font-weight: 700;
                justify-content: center;
                margin: 6px 0 6px;
                min-height: 42px;
                padding: 8px 12px;
                text-align: center;
            }

            .question-type-active {
                background: #fff5f5;
                border: 2px solid #ef4444;
                color: #dc2626;
                box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.18);
            }

            .question-type-inactive {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                color: #111827;
            }

            div[data-testid="stPills"],
            div[data-testid="stPills"] *,
            div[data-testid="stPills"] *::before,
            div[data-testid="stPills"] *::after {
                background-color: #ffffff !important;
                color: #111827 !important;
                text-shadow: none !important;
            }

            div[data-testid="stPills"] button,
            div[data-testid="stPills"] [role="option"],
            div[data-testid="stPills"] [role="button"],
            div[data-testid="stPills"] label {
                background: #ffffff !important;
                background-color: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                color: #111827 !important;
                font-weight: 500 !important;
                box-shadow: none !important;
            }

            div[data-testid="stPills"] button:hover,
            div[data-testid="stPills"] [role="option"]:hover,
            div[data-testid="stPills"] [role="button"]:hover,
            div[data-testid="stPills"] label:hover {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stPills"] button[aria-pressed="true"],
            div[data-testid="stPills"] button[aria-selected="true"],
            div[data-testid="stPills"] [role="option"][aria-selected="true"],
            div[data-testid="stPills"] [role="button"][aria-pressed="true"],
            div[data-testid="stPills"] label:has(input:checked) {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border: 2px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 700 !important;
                box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.16) !important;
            }

            div[data-testid="stButton"] button[kind="secondary"],
            .stButton > button[kind="secondary"] {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                color: #111827 !important;
            }

            div[data-testid="stButton"] button[kind="secondary"]:hover,
            .stButton > button[kind="secondary"]:hover {
                background: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            .index-step-label {
                color: #101820;
                font-size: 0.96rem;
                font-weight: 850;
                margin: 16px 0 8px;
            }

            .index-file-row {
                background: #ffffff;
                border: 1px solid #d8e2eb;
                border-radius: 8px;
                margin-bottom: 8px;
                padding: 10px 12px;
            }

            .index-file-row strong {
                color: #101820;
                display: block;
                overflow-wrap: anywhere;
            }

            .index-file-row span {
                color: #475467;
                display: block;
                margin-top: 4px;
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
                border: 1px solid #cbd8e4;
                border-left: 6px solid #ef5b5b;
                border-radius: 8px;
                color: #1f2933;
                display: grid;
                gap: 12px;
                padding: 16px 18px;
                box-shadow: 0 8px 18px rgba(16, 24, 32, 0.08);
            }

            .source-card strong {
                color: #101820;
            }

            .source-card-title {
                color: #101820;
                font-size: 1rem;
                font-weight: 850;
                line-height: 1.3;
            }

            .source-meta-grid {
                display: grid;
                gap: 10px;
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }

            .source-meta-grid div {
                background: #f7fafc;
                border: 1px solid #dde7ef;
                border-radius: 6px;
                min-height: 64px;
                padding: 9px 10px;
            }

            .source-meta-extra {
                background: #f7fafc;
                border: 1px solid #dde7ef;
                border-radius: 6px;
                max-width: 220px;
                padding: 9px 10px;
            }

            .source-meta-grid span {
                color: #667085;
                display: block;
                font-size: 0.72rem;
                font-weight: 800;
                margin-bottom: 5px;
                text-transform: uppercase;
            }

            .source-meta-grid strong {
                display: block;
                font-size: 0.92rem;
                line-height: 1.25;
                overflow-wrap: anywhere;
            }

            .source-excerpt {
                border-top: 1px solid #edf2f7;
                color: #344054;
                font-size: 0.98rem;
                line-height: 1.58;
                margin-top: 4px;
                padding-top: 12px;
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

            /* Final override: segmented controls must stay light in normal, active, and hover states. */
            div[data-testid="stSegmentedControl"],
            div[data-testid="stSegmentedControl"] > div,
            div[data-testid="stSegmentedControl"] [data-baseweb],
            div[data-testid="stSegmentedControl"] [data-baseweb] > div,
            div[data-testid="stSegmentedControl"] [role="radiogroup"],
            div[data-testid="stSegmentedControl"] [role="group"] {
                background: #ffffff !important;
                background-color: #ffffff !important;
                border-color: #cbd5e1 !important;
                color: #111827 !important;
                box-shadow: none !important;
            }

            div[data-testid="stSegmentedControl"] *,
            div[data-testid="stSegmentedControl"] *::before,
            div[data-testid="stSegmentedControl"] *::after {
                background: #ffffff !important;
                background-color: #ffffff !important;
                color: #111827 !important;
                box-shadow: none !important;
                text-shadow: none !important;
            }

            div[data-testid="stSegmentedControl"] button,
            div[data-testid="stSegmentedControl"] [role="radio"],
            div[data-testid="stSegmentedControl"] [role="option"],
            div[data-testid="stSegmentedControl"] [role="button"],
            div[data-testid="stSegmentedControl"] label,
            div[data-testid="stSegmentedControl"] label > div,
            div[data-testid="stSegmentedControl"] label > div > div {
                background: #f8fafc !important;
                background-color: #f8fafc !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                color: #111827 !important;
                font-weight: 600 !important;
                box-shadow: none !important;
                opacity: 1 !important;
            }

            div[data-testid="stSegmentedControl"] button *,
            div[data-testid="stSegmentedControl"] [role="radio"] *,
            div[data-testid="stSegmentedControl"] [role="option"] *,
            div[data-testid="stSegmentedControl"] [role="button"] *,
            div[data-testid="stSegmentedControl"] label * {
                background: transparent !important;
                background-color: transparent !important;
                color: inherit !important;
                fill: currentColor !important;
            }

            div[data-testid="stSegmentedControl"] button:hover,
            div[data-testid="stSegmentedControl"] [role="radio"]:hover,
            div[data-testid="stSegmentedControl"] [role="option"]:hover,
            div[data-testid="stSegmentedControl"] [role="button"]:hover,
            div[data-testid="stSegmentedControl"] label:hover,
            div[data-testid="stSegmentedControl"] label:hover > div,
            div[data-testid="stSegmentedControl"] label:hover > div > div {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
            div[data-testid="stSegmentedControl"] button[aria-selected="true"],
            div[data-testid="stSegmentedControl"] button[aria-checked="true"],
            div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
            div[data-testid="stSegmentedControl"] [role="option"][aria-selected="true"],
            div[data-testid="stSegmentedControl"] [role="button"][aria-pressed="true"],
            div[data-testid="stSegmentedControl"] label:has(input:checked),
            div[data-testid="stSegmentedControl"] label:has(input:checked) > div,
            div[data-testid="stSegmentedControl"] label:has(input:checked) > div > div {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border: 1px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 600 !important;
                box-shadow: inset 0 0 0 1px #ef4444 !important;
            }

            div[data-testid="stSegmentedControl"] [aria-pressed="false"],
            div[data-testid="stSegmentedControl"] [aria-selected="false"],
            div[data-testid="stSegmentedControl"] [aria-checked="false"],
            div[data-testid="stSegmentedControl"] label:not(:has(input:checked)) {
                background: #f8fafc !important;
                background-color: #f8fafc !important;
                border-color: #cbd5e1 !important;
                color: #111827 !important;
            }

            div[data-testid="stSegmentedControl"] svg {
                color: #111827 !important;
                fill: #111827 !important;
                background: transparent !important;
            }

            /* Last-mile default-state reset: no interactive control may be dark without hover. */
            .stApp button,
            .stApp button:hover,
            .stApp button:focus,
            .stApp button:active,
            .stApp [role="button"],
            .stApp [role="button"]:hover,
            .stApp [role="button"]:focus,
            .stApp [role="button"]:active,
            .stApp [role="radio"],
            .stApp [role="radio"]:hover,
            .stApp [role="radio"]:focus,
            .stApp [role="radio"]:active,
            .stApp div[data-baseweb="radio"] label,
            .stApp div[data-baseweb="radio"] label:hover,
            .stApp div[data-baseweb="radio"] label:focus,
            .stApp div[data-baseweb="radio"] label:active,
            .stApp div[data-baseweb="radio"] label > div,
            .stApp div[data-baseweb="radio"] label > div > div {
                background: #ffffff !important;
                background-color: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                color: #111827 !important;
                box-shadow: none !important;
                text-shadow: none !important;
            }

            .stApp button:hover,
            .stApp [role="button"]:hover,
            .stApp [role="radio"]:hover,
            .stApp div[data-baseweb="radio"] label:hover {
                background: #fee2e2 !important;
                background-color: #fee2e2 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            .stApp button[kind="primary"],
            .stApp .stButton > button[kind="primary"],
            .stApp div[data-testid="stButton"] button[kind="primary"] {
                background: #ef5b5b !important;
                background-color: #ef5b5b !important;
                border: 1px solid #ef5b5b !important;
                color: #ffffff !important;
                font-weight: 850 !important;
            }

            .stApp button[kind="primary"] *,
            .stApp .stButton > button[kind="primary"] *,
            .stApp div[data-testid="stButton"] button[kind="primary"] * {
                color: #ffffff !important;
            }

            .stApp button:disabled,
            .stApp button:disabled:hover,
            .stApp [aria-disabled="true"],
            .stApp [aria-disabled="true"]:hover {
                background: #f1f5f9 !important;
                background-color: #f1f5f9 !important;
                border: 1px solid #cbd5e1 !important;
                color: #64748b !important;
                opacity: 1 !important;
            }

            .stApp [role="tab"],
            .stApp [role="tab"]:hover,
            .stApp [role="tab"]:focus,
            .stApp [role="tab"]:active {
                background: #ffffff !important;
                background-color: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                color: #111827 !important;
                box-shadow: none !important;
            }

            .stApp [role="tab"][aria-selected="true"] {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border: 1px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 600 !important;
            }

            .stApp [role="tab"] *,
            .stApp button *,
            .stApp [role="button"] *,
            .stApp [role="radio"] *,
            .stApp div[data-baseweb="radio"] label * {
                color: inherit !important;
                text-shadow: none !important;
            }

            .stApp div[data-testid="stSegmentedControl"],
            .stApp div[data-testid="stSegmentedControl"] *,
            .stApp div[data-testid="stSegmentedControl"] *::before,
            .stApp div[data-testid="stSegmentedControl"] *::after {
                background-color: #ffffff !important;
                color: #111827 !important;
                text-shadow: none !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button,
            .stApp div[data-testid="stSegmentedControl"] [role="radio"],
            .stApp div[data-testid="stSegmentedControl"] [role="button"],
            .stApp div[data-testid="stSegmentedControl"] [role="option"],
            .stApp div[data-testid="stSegmentedControl"] label {
                background: #f8fafc !important;
                background-color: #f8fafc !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                color: #111827 !important;
                font-weight: 600 !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button:hover,
            .stApp div[data-testid="stSegmentedControl"] [role="radio"]:hover,
            .stApp div[data-testid="stSegmentedControl"] [role="button"]:hover,
            .stApp div[data-testid="stSegmentedControl"] [role="option"]:hover,
            .stApp div[data-testid="stSegmentedControl"] label:hover {
                background: #fee2e2 !important;
                background-color: #fee2e2 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
            .stApp div[data-testid="stSegmentedControl"] button[aria-selected="true"],
            .stApp div[data-testid="stSegmentedControl"] button[aria-checked="true"],
            .stApp div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
            .stApp div[data-testid="stSegmentedControl"] [role="button"][aria-pressed="true"],
            .stApp div[data-testid="stSegmentedControl"] [role="option"][aria-selected="true"],
            .stApp div[data-testid="stSegmentedControl"] label:has(input:checked) {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border: 1px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 600 !important;
            }

            /* True mobile-style toggles: always visible, never dark/hidden until hover. */
            .stApp div[data-testid="stToggle"] {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 10px !important;
                padding: 14px 16px !important;
                box-shadow: 0 1px 2px rgba(16, 24, 32, 0.06) !important;
            }

            .stApp div[data-testid="stToggle"] label,
            .stApp div[data-testid="stToggle"] label * {
                background: transparent !important;
                color: #111827 !important;
                font-weight: 700 !important;
            }

            .stApp div[data-testid="stToggle"] [role="switch"],
            .stApp div[data-testid="stToggle"] input + div {
                background: #e5e7eb !important;
                background-color: #e5e7eb !important;
                border: 1px solid #94a3b8 !important;
                border-radius: 999px !important;
                box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.16) !important;
                min-height: 28px !important;
                min-width: 54px !important;
                opacity: 1 !important;
            }

            .stApp div[data-testid="stToggle"] [role="switch"][aria-checked="true"],
            .stApp div[data-testid="stToggle"] input:checked + div {
                background: #ef4444 !important;
                background-color: #ef4444 !important;
                border-color: #dc2626 !important;
                box-shadow: inset 0 1px 2px rgba(127, 29, 29, 0.24) !important;
            }

            .stApp div[data-testid="stToggle"] [role="switch"] *,
            .stApp div[data-testid="stToggle"] input + div * {
                opacity: 1 !important;
            }

            /* Fragetyp segmented control: inactive stays white, active is clearly outlined. */
            .stApp div[data-testid="stSegmentedControl"] {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                padding: 4px !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button,
            .stApp div[data-testid="stSegmentedControl"] [role="radio"],
            .stApp div[data-testid="stSegmentedControl"] [role="button"],
            .stApp div[data-testid="stSegmentedControl"] label {
                background: #ffffff !important;
                background-color: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                color: #111827 !important;
                font-weight: 500 !important;
                box-shadow: none !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
            .stApp div[data-testid="stSegmentedControl"] button[aria-selected="true"],
            .stApp div[data-testid="stSegmentedControl"] button[aria-checked="true"],
            .stApp div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
            .stApp div[data-testid="stSegmentedControl"] [role="button"][aria-pressed="true"],
            .stApp div[data-testid="stSegmentedControl"] label:has(input:checked) {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border: 2px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 700 !important;
                box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.16) !important;
            }

            .stApp div[data-testid="stSegmentedControl"] button:hover,
            .stApp div[data-testid="stSegmentedControl"] [role="radio"]:hover,
            .stApp div[data-testid="stSegmentedControl"] [role="button"]:hover,
            .stApp div[data-testid="stSegmentedControl"] label:hover {
                background: #fff5f5 !important;
                background-color: #fff5f5 !important;
                border-color: #ef4444 !important;
                color: #dc2626 !important;
            }

            /* Single clean question-type row. */
            .stApp div[data-testid="stPills"],
            .stApp div[data-testid="stPills"] * {
                background: transparent !important;
                color: #111827 !important;
            }

            .stApp div[data-testid="stPills"] button,
            .stApp div[data-testid="stPills"] [role="option"],
            .stApp div[data-testid="stPills"] [role="button"] {
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                border-radius: 999px !important;
                color: #111827 !important;
                font-weight: 500 !important;
                box-shadow: none !important;
            }

            .stApp div[data-testid="stPills"] button[aria-pressed="true"],
            .stApp div[data-testid="stPills"] button[aria-selected="true"],
            .stApp div[data-testid="stPills"] [role="option"][aria-selected="true"],
            .stApp div[data-testid="stPills"] [role="button"][aria-pressed="true"] {
                background: #fff5f5 !important;
                border: 2px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 700 !important;
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

                .source-meta-grid {
                    grid-template-columns: 1fr 1fr;
                }

                .index-success-grid,
                .index-summary {
                    grid-template-columns: 1fr 1fr;
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

                .source-meta-grid {
                    grid-template-columns: 1fr;
                }

                .index-success-grid,
                .index-summary {
                    grid-template-columns: 1fr;
                }
            }

            /* ---------------------------------------------------------------
               Final overrides (must stay last so they win the cascade).
               Fix two GUI-wide issues:
               1. Empty "?" help boxes: Streamlit renders each help tooltip as a
                  <button>, which the catch-all button styling above painted as an
                  empty 18x18 white bordered box (the icon only appeared on hover).
                  Hide the help icons everywhere so no empty boxes remain.
               2. Toggles invisible until hover: st.toggle renders as
                  data-testid="stCheckbox" (not "stToggle"), so every stToggle rule
                  above never matched. The switch fell back to BaseWeb's default,
                  whose OFF track is ~15% opacity (near-invisible on white) and only
                  darkens on hover. Give the track and knob a solid, always-visible
                  look in both OFF and ON states.
               --------------------------------------------------------------- */
            [data-testid="stTooltipIcon"],
            [data-testid="stTooltipHoverTarget"] {
                display: none !important;
            }

            [data-testid="stCheckbox"] label[data-baseweb="checkbox"] > div:first-child {
                background: #cbd5e1 !important;
                border: 1px solid #94a3b8 !important;
                box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.12) !important;
                opacity: 1 !important;
            }

            [data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > div:first-child {
                background: #ef5b5b !important;
                border-color: #d94848 !important;
            }

            [data-testid="stCheckbox"] label[data-baseweb="checkbox"] > div:first-child > div {
                background: #ffffff !important;
                border: 1px solid #94a3b8 !important;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.25) !important;
                opacity: 1 !important;
            }

            [data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > div:first-child > div {
                border-color: #d94848 !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
