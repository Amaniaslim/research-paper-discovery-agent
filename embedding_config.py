"""Central embedding configuration for PDF-RAG.

Goal: one place that decides how text is turned into vectors, with a *safe*
fallback so the app never crashes if a heavier model is missing.

Behaviour:
- The active model is read from the ``EMBEDDING_MODEL`` environment variable.
- ``local`` / empty (the default) -> deterministic offline lexical hash embedding
  (the original Sprint 3 behaviour, no extra dependencies).
- Any other value -> treated as a sentence-transformers model name and loaded
  lazily. If sentence-transformers (or the model) cannot be loaded, we fall back
  to the local embedding and remember that, so the UI can show what is really
  active.

Store and query always go through :func:`embed_text`, so vectors are consistent
within a single index. If you switch models, rebuild the index.
"""

from __future__ import annotations

import os

# A sensible "better" default users can opt into by setting
# EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RECOMMENDED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LOCAL_MODEL_LABEL = "local-lexical-hash (64d, offline)"

_LOCAL_VALUES = {"", "local", "local-hash", "offline", "default"}

# Cache so we only try to load the heavy model once per process.
_st_model = None
_st_model_name: str | None = None
_st_load_failed = False


def configured_model_name() -> str:
    """Raw EMBEDDING_MODEL value (may be empty for local)."""
    return os.getenv("EMBEDDING_MODEL", "").strip()


def _wants_local(name: str) -> bool:
    return name.lower() in _LOCAL_VALUES


def _load_sentence_transformer(name: str):
    """Try to load a sentence-transformers model; return None on any failure."""
    global _st_model, _st_model_name, _st_load_failed
    if _st_load_failed and _st_model_name == name:
        return None
    if _st_model is not None and _st_model_name == name:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer

        _st_model = SentenceTransformer(name)
        _st_model_name = name
        _st_load_failed = False
        return _st_model
    except Exception:
        _st_model = None
        _st_model_name = name
        _st_load_failed = True
        return None


def active_model_label() -> str:
    """Human-readable label of the embedding model that is actually in use."""
    name = configured_model_name()
    if _wants_local(name):
        return LOCAL_MODEL_LABEL
    model = _load_sentence_transformer(name)
    if model is None:
        return f"{LOCAL_MODEL_LABEL} (fallback: '{name}' unavailable)"
    return f"{name} (sentence-transformers)"


def using_local_fallback() -> bool:
    name = configured_model_name()
    if _wants_local(name):
        return True
    return _load_sentence_transformer(name) is None


def embed_text(text: str) -> list[float]:
    """Embed a single text with the active model, falling back safely to local."""
    name = configured_model_name()
    if not _wants_local(name):
        model = _load_sentence_transformer(name)
        if model is not None:
            try:
                vector = model.encode(text or "", normalize_embeddings=True)
                return [float(value) for value in vector]
            except Exception:
                pass  # fall through to local embedding
    # Import lazily to avoid a circular import with rag_store.
    import rag_store

    return rag_store.local_embedding(text or "")
