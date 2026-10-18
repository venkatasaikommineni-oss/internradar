"""Optional semantic similarity (sentence-transformers). Off by default; never required.

Enable with ``configure(enabled=True)`` or env ``INTERNRADAR_ENABLE_SEMANTIC=true``.
Any failure (package missing, model download blocked) degrades to ``None`` so the
transparent baseline score keeps working.
"""
from functools import lru_cache
import logging
import os

log = logging.getLogger("internradar.ai.semantic")

_state = {"enabled": None, "model": None, "broken": False}


def configure(enabled: bool | None = None, model: str | None = None) -> None:
    """Explicit switch (used by the app so .env settings work, not just os.environ)."""
    if enabled is not None:
        _state["enabled"] = enabled
        _state["broken"] = False
    if model:
        _state["model"] = model
        _model.cache_clear()
        _embedding.cache_clear()


def is_enabled() -> bool:
    if _state["broken"]:
        return False
    if _state["enabled"] is not None:
        return bool(_state["enabled"])
    return os.getenv("INTERNRADAR_ENABLE_SEMANTIC", "false").lower() in {"1", "true", "yes"}


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    name = _state["model"] or os.getenv("INTERNRADAR_SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    return SentenceTransformer(name)


@lru_cache(maxsize=8192)
def _embedding(text: str) -> tuple[float, ...]:
    vec = _model().encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return tuple(float(x) for x in vec)


def _profile_text(user) -> str:
    roles = ", ".join(getattr(user, "desired_roles", None) or [])
    skills = ", ".join(getattr(user, "skills", None) or [])
    return f"Internship roles wanted: {roles}. Skills: {skills}."


def _listing_text(it) -> str:
    return (f"Internship: {getattr(it, 'title', '') or ''}. Skills: {', '.join(getattr(it, 'skills', None) or [])}. "
            f"{(getattr(it, 'description', '') or '')[:1500]}")


def semantic_similarity(user, it) -> float | None:
    """Return similarity in [0,1] or None when disabled/unavailable.

    Raw MiniLM cosine for related texts sits around 0.3-0.7 and unrelated ~0-0.15, so
    it is rescaled from that band instead of the naive (cos+1)/2 which compresses
    everything into 0.5-0.85 and hides real differences."""
    if not is_enabled():
        return None
    profile, listing = _profile_text(user), _listing_text(it)
    if len(profile) < 30 or len(listing) < 20:
        return None
    try:
        a, b = _embedding(profile), _embedding(listing)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        log.warning("Semantic model unavailable; using baseline scoring: %s", exc)
        _state["broken"] = True
        return None
    if not a or len(a) != len(b):
        return None
    cos = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, (cos - 0.10) / 0.60))
