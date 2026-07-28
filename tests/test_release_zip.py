from __future__ import annotations

from zipfile import ZipFile

from scripts import create_final_zip


def test_release_zip_is_allowlisted(monkeypatch, tmp_path) -> None:
    archive_path = tmp_path / "Research_Paper_Discovery_Agent_Final.zip"
    monkeypatch.setattr(create_final_zip, "RELEASE_DIR", tmp_path)
    monkeypatch.setattr(create_final_zip, "ARCHIVE_PATH", archive_path)

    result = create_final_zip.build_archive()

    assert result == archive_path
    with ZipFile(result) as archive:
        names = set(archive.namelist())
    assert "app.py" in names
    assert "compose.yaml" in names
    assert "scripts/smoke_check.py" in names
    assert "README.md" in names
    assert "docs/index.html" in names
    assert "scripts/create_final_zip.py" in names
    assert "app_sprint3.py" not in names
    assert "docker-compose.yml" not in names
    assert ".env" not in names
    assert not any(name.startswith(".git/") for name in names)
    assert not any(name.startswith("demo_output/") for name in names)
