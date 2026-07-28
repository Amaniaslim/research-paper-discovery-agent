from __future__ import annotations

import history_store


def test_history_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(history_store, "HISTORY_PATH", tmp_path / "history.json")

    entry_id = history_store.upsert_entry(
        None,
        "Agentic security",
        {"research_query": "agentic AI security"},
    )
    assert history_store.get_entry(entry_id)["payload"]["research_query"] == "agentic AI security"

    assert history_store.rename_entry(entry_id, "Renamed research") is True
    assert history_store.list_entries()[0]["title"] == "Renamed research"

    history_store.delete_entry(entry_id)
    assert history_store.list_entries() == []
