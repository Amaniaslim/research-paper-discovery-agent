# Sprint 2 - Research Paper Discovery Agent

This project is a Streamlit demo for a research agent that finds, ranks,
summarizes, remembers, and exports papers for a research question.

## What The Agent Does

1. The user enters a research question.
2. The agent expands common German query terms into English search terms.
3. It tries live retrieval from arXiv.
4. If arXiv does not return stable results, it tries Semantic Scholar.
5. If live APIs fail, it uses the local cache or embedded demo papers.
6. It normalizes title, authors, year, abstract, source, URL, and score.
7. It deduplicates papers by stable IDs.
8. It ranks papers by title matches, abstract matches, topic relevance, and recency.
9. It generates short heuristic summaries from abstracts.
10. It stores previous research runs in ChromaDB, with JSON as fallback.
11. It exports a Markdown review.

## Technologies

- Python
- Streamlit
- arXiv API
- Semantic Scholar API
- ChromaDB
- JSON cache
- Markdown export

## Project Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit user interface |
| `paper_research_agent.py` | Sprint 2 retrieval, ranking, fallback, and export workflow |
| `review_core.py` | Shared paper models, demo papers, ranking helpers, and summaries |
| `memory_store.py` | ChromaDB memory with JSON fallback |
| `sprint1_app.py` | Optional old Sprint 1 UI kept for reference |
| `SPRINT1_NOTES.md` | Sprint 1 documentation kept for context |
| `demo_output/paper_cache.json` | Optional local paper cache for stable demos |

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run The App

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py
```

If port `8501` is already used:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\app.py --server.port 8502
```

## Run From Terminal

```powershell
.\.venv\Scripts\python.exe .\paper_research_agent.py
```

Offline/cache fallback mode:

```powershell
.\.venv\Scripts\python.exe .\paper_research_agent.py --offline
```

## Current Limits

Sprint 2 works with paper metadata and abstracts. It does not yet analyze full
PDFs, use full-text RAG, or generate LLM-based summaries.
