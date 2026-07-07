"""OCR adapter for scanned PDFs.

This module isolates all OCR handling so the rest of the app never has to know
which backend is used. It supports three modes, selected via the ``OCR_MODE``
environment variable:

- ``disabled``      -> no OCR, scanned pages stay empty (default, safe)
- ``tesseract``     -> local Tesseract OCR (needs pytesseract + Tesseract binary)
- ``unlimited_ocr`` -> Baidu Unlimited-OCR, either as an OpenAI-compatible HTTP
                       endpoint (``UNLIMITED_OCR_BASE_URL``) or as a local CLI
                       command (``UNLIMITED_OCR_PATH``)

The professor feedback pointed at https://github.com/baidu/Unlimited-OCR. That
project is run as a separate server/CLI outside this Streamlit app. We never
hardcode absolute paths: the command/URL is always read from the environment.

Design rules:
- OCR is optional. Text PDFs must keep working even if nothing here is installed.
- Nothing in here raises on a missing backend. Callers get an empty string and a
  helpful availability flag/message instead of a crash.
"""

from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# Public constants so callers/UI can reference the canonical mode names.
MODE_DISABLED = "disabled"
MODE_TESSERACT = "tesseract"
MODE_UNLIMITED = "unlimited_ocr"
VALID_MODES = (MODE_DISABLED, MODE_TESSERACT, MODE_UNLIMITED)


def get_ocr_mode() -> str:
    """Return the configured OCR mode from the OCR_MODE env var (safe default)."""
    mode = os.getenv("OCR_MODE", MODE_DISABLED).strip().lower()
    if mode in {"unlimited-ocr", "unlimited", "baidu"}:
        mode = MODE_UNLIMITED
    return mode if mode in VALID_MODES else MODE_DISABLED


def normalize_provider(provider: str | None) -> str:
    """Map a UI provider label to a canonical provider name."""
    if not provider:
        return MODE_TESSERACT
    provider = provider.strip().lower()
    if provider in {MODE_UNLIMITED, "unlimited-ocr", "unlimited", "baidu"}:
        return MODE_UNLIMITED
    return MODE_TESSERACT


def tesseract_available() -> bool:
    """True when local Tesseract OCR can actually be used."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def unlimited_ocr_available() -> bool:
    """True when an Unlimited-OCR backend (HTTP endpoint or CLI) is configured."""
    return bool(_unlimited_base_url() or _unlimited_cli_path())


def provider_available(provider: str) -> bool:
    provider = normalize_provider(provider)
    if provider == MODE_UNLIMITED:
        return unlimited_ocr_available()
    return tesseract_available()


def describe_backend(provider: str) -> str:
    """Short, human-readable status string for the UI."""
    provider = normalize_provider(provider)
    if provider == MODE_UNLIMITED:
        if _unlimited_base_url():
            return f"Unlimited-OCR HTTP endpoint: {_unlimited_base_url()}"
        if _unlimited_cli_path():
            return f"Unlimited-OCR CLI: {_unlimited_cli_path()}"
        return (
            "Unlimited-OCR selected but not configured. Set UNLIMITED_OCR_BASE_URL "
            "or UNLIMITED_OCR_PATH."
        )
    return "Tesseract local" if tesseract_available() else "Tesseract local (not installed)"


def ocr_image_bytes(image_png: bytes, provider: str = MODE_TESSERACT) -> str:
    """Run OCR on a single PNG image and return recognised text (never raises)."""
    provider = normalize_provider(provider)
    try:
        if provider == MODE_UNLIMITED:
            return _unlimited_ocr(image_png)
        return _tesseract_ocr(image_png)
    except Exception:
        # OCR must never crash the indexing pipeline.
        return ""


# --------------------------------------------------------------------------- #
# Tesseract backend
# --------------------------------------------------------------------------- #
def _tesseract_ocr(image_png: bytes) -> str:
    try:
        import io

        import pytesseract
        from PIL import Image
    except ImportError:
        return ""
    image = Image.open(io.BytesIO(image_png))
    try:
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Unlimited-OCR backend (HTTP endpoint preferred, CLI fallback)
# --------------------------------------------------------------------------- #
def _unlimited_ocr(image_png: bytes) -> str:
    if _unlimited_base_url():
        text = _unlimited_ocr_http(image_png)
        if text:
            return text
    if _unlimited_cli_path():
        return _unlimited_ocr_cli(image_png)
    return ""


def _unlimited_base_url() -> str:
    return os.getenv("UNLIMITED_OCR_BASE_URL", "").strip().rstrip("/")


def _unlimited_cli_path() -> str:
    return os.getenv("UNLIMITED_OCR_PATH", "").strip()


def _unlimited_ocr_http(image_png: bytes) -> str:
    """Call an OpenAI-compatible Unlimited-OCR server (vLLM/SGLang style)."""
    base_url = _unlimited_base_url()
    if not base_url:
        return ""
    model = os.getenv("UNLIMITED_OCR_MODEL", "Unlimited-OCR").strip()
    api_key = os.getenv("UNLIMITED_OCR_API_KEY", "").strip()
    encoded = base64.b64encode(image_png).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Parse this document page and return only the recognized text."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
                ],
            }
        ],
        "temperature": 0,
        "max_tokens": 32768,
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "ResearchPaperDiscoveryAgent/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        return response_payload["choices"][0]["message"]["content"].strip()
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return ""


def _unlimited_ocr_cli(image_png: bytes) -> str:
    """Run a local Unlimited-OCR CLI command on the rendered page image.

    The command template is read from UNLIMITED_OCR_PATH. Use ``{image}`` as a
    placeholder for the temporary PNG path, e.g.::

        UNLIMITED_OCR_PATH="python /opt/Unlimited-OCR/run.py --image {image}"

    If no placeholder is given, the image path is appended as the last argument.
    Recognised text is read from stdout.
    """
    command_template = _unlimited_cli_path()
    if not command_template:
        return ""
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            handle.write(image_png)
            tmp_path = Path(handle.name)
        if "{image}" in command_template:
            command = shlex.split(command_template.replace("{image}", str(tmp_path)))
        else:
            command = shlex.split(command_template) + [str(tmp_path)]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("UNLIMITED_OCR_TIMEOUT", "300")),
            check=False,
        )
        return (completed.stdout or "").strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
