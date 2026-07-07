"""Local chat-style history for research sessions.

Stores lightweight, JSON-serializable snapshots of a session (research query,
PDF question, grounded answer, retrieved sources, index stats and the exported
markdown) so the sidebar can list past sessions and reopen, rename or delete
them - similar to a chat history.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
HISTORY_PATH = PROJECT_DIR / "demo_output" / "history.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _load() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save(entries: list[dict]) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def list_entries() -> list[dict]:
    """Return all history entries, newest first."""
    return sorted(_load(), key=lambda entry: str(entry.get("updated_at", "")), reverse=True)


def get_entry(entry_id: str) -> dict | None:
    for entry in _load():
        if entry.get("id") == entry_id:
            return entry
    return None


def upsert_entry(entry_id: str | None, title: str, payload: dict) -> str:
    """Create a new entry or update an existing one; returns the entry id."""
    entries = _load()
    if entry_id:
        for entry in entries:
            if entry.get("id") == entry_id:
                entry["title"] = title or entry.get("title", "Recherche")
                entry["payload"] = payload
                entry["updated_at"] = _now()
                _save(entries)
                return entry_id
    new_id = uuid.uuid4().hex
    entries.append(
        {
            "id": new_id,
            "title": title or "Neue Recherche",
            "created_at": _now(),
            "updated_at": _now(),
            "payload": payload,
        }
    )
    _save(entries)
    return new_id


def rename_entry(entry_id: str, title: str) -> bool:
    entries = _load()
    for entry in entries:
        if entry.get("id") == entry_id:
            entry["title"] = title or entry.get("title", "Recherche")
            entry["updated_at"] = _now()
            _save(entries)
            return True
    return False


def delete_entry(entry_id: str) -> None:
    _save([entry for entry in _load() if entry.get("id") != entry_id])
