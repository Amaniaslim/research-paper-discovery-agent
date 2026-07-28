"""Build the sanitized final-delivery archive.

The archive is assembled from an allowlist instead of copying the repository
tree. Local secrets, uploaded PDFs, runtime databases, caches, credentials, Git
metadata, and the release directory can therefore never be included by a broad
recursive copy.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = PROJECT_ROOT / "release"
ARCHIVE_PATH = RELEASE_DIR / "Research_Paper_Discovery_Agent_Final.zip"

ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "compose.yaml",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
}
INCLUDED_DIRECTORIES = ("tests", "docs", "scripts")
EXCLUDED_DIRECTORY_NAMES = {
    ".agents",
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "demo_output",
    "dist",
    "release",
    "venv",
}
EXCLUDED_FILE_NAMES = {
    ".env",
    "secrets.toml",
}
EXCLUDED_SUFFIXES = {
    ".key",
    ".log",
    ".pem",
    ".pyc",
    ".pyo",
    ".zip",
}
ALLOWED_PDF = Path("docs/assets/Research_Paper_Discovery_Agent_Demo_Day.pdf")


def _is_safe(relative_path: Path) -> bool:
    """Return True only for files allowed in the public delivery."""
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return False
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in relative_path.parts):
        return False
    if relative_path.name in EXCLUDED_FILE_NAMES:
        return False
    if relative_path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if relative_path.suffix.lower() == ".pdf" and relative_path != ALLOWED_PDF:
        return False
    lowered = relative_path.name.lower()
    if "credential" in lowered or "private_key" in lowered:
        return False
    return True


def _candidate_files() -> set[Path]:
    """Collect source and delivery files from explicit roots."""
    candidates = {
        path.relative_to(PROJECT_ROOT)
        for path in PROJECT_ROOT.glob("*.py")
        if path.is_file()
    }
    candidates.update(Path(name) for name in ROOT_FILES)
    candidates.add(Path("data/pdfs/.gitkeep"))

    for directory_name in INCLUDED_DIRECTORIES:
        directory = PROJECT_ROOT / directory_name
        if not directory.exists():
            continue
        candidates.update(
            path.relative_to(PROJECT_ROOT)
            for path in directory.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
    return candidates


def build_archive() -> Path:
    """Create the final ZIP and return its absolute path."""
    missing = sorted(
        str(path)
        for path in (Path(name) for name in ROOT_FILES)
        if not (PROJECT_ROOT / path).is_file()
    )
    if missing:
        raise FileNotFoundError(f"Required delivery files are missing: {', '.join(missing)}")

    files = sorted(
        (
            relative_path
            for relative_path in _candidate_files()
            if _is_safe(relative_path) and (PROJECT_ROOT / relative_path).is_file()
        ),
        key=lambda path: path.as_posix(),
    )
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative_path in files:
            archive.write(PROJECT_ROOT / relative_path, relative_path.as_posix())

    print(f"Created: {ARCHIVE_PATH}")
    print(f"Files: {len(files)}")
    print(f"Size: {ARCHIVE_PATH.stat().st_size / (1024 * 1024):.2f} MB")
    return ARCHIVE_PATH


if __name__ == "__main__":
    build_archive()
