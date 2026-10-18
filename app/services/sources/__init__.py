import json
import logging
import os
import pathlib
import re

from ...config import settings
from .adzuna import AdzunaSource
from .ats import AshbySource, GreenhouseSource, LeverSource
from .base import JSONFeedSource, ListSource, RemotiveSource, dig, http_get_json  # noqa: F401
from .web import JobPostingPagesSource, RSSSource

log = logging.getLogger("internradar.sources")

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REQUIRED = {
    "json_feed": ("name", "url", "field_map"),
    "greenhouse": ("boards",),
    "lever": ("companies",),
    "ashby": ("boards",),
    "rss": ("name", "url"),
    "jobposting_pages": ("name",),
    "web_pages": ("name",),
    "adzuna": (),
}


def _expand(v):
    """${NAME} -> environment variable, so API keys/tokens never sit in sources.json.
    A missing variable is an error (never silently empty)."""
    if isinstance(v, str):
        def sub(m):
            if m.group(1) not in os.environ:
                raise ValueError(f"environment variable {m.group(1)} is not set")
            return os.environ[m.group(1)]

        return _ENV.sub(sub, v)
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_expand(x) for x in v]
    return v


def _item(x):
    """'token' or {'token': 'x', 'company': 'Display Name'} -> (token, company|None)"""
    token, company = (x, None) if isinstance(x, str) else (x["token"], x.get("company"))
    if not _TOKEN.match(str(token)):
        raise ValueError(f"invalid board token {token!r}")
    return str(token), company


def build_sources(cfg: dict) -> list:
    t = cfg.get("type", "json_feed")
    if t not in _REQUIRED:
        raise ValueError(f"unknown source type '{t}'")
    missing = [k for k in _REQUIRED[t] if not cfg.get(k)]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}")
    if t == "json_feed":
        return [JSONFeedSource(cfg)]
    if t == "greenhouse":
        return [GreenhouseSource(*_item(b), details=bool(cfg.get("details", True))) for b in cfg["boards"]]
    if t == "lever":
        return [LeverSource(*_item(c), region=cfg.get("region")) for c in cfg["companies"]]
    if t == "ashby":
        return [AshbySource(*_item(b)) for b in cfg["boards"]]
    if t == "rss":
        return [RSSSource(cfg)]
    if t == "adzuna":
        return [AdzunaSource(cfg)]
    if not (cfg.get("pages") or cfg.get("sitemaps")):
        raise ValueError("needs 'pages' and/or 'sitemaps'")
    return [JobPostingPagesSource(cfg)]


def _load_configs() -> tuple[list[dict], list[str]]:
    cfgs, errors = list(settings.feed_sources), []
    p = pathlib.Path(settings.sources_file)
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cfgs += data["sources"] if isinstance(data, dict) else data
        except (OSError, ValueError, KeyError, TypeError) as e:
            errors.append(f"{p}: could not be read ({type(e).__name__}: {e})")
    return [c for c in cfgs if isinstance(c, dict) and c.get("enabled", True)], errors


def load_sources() -> tuple[list, list[str]]:
    """-> (sources, config errors). A bad entry is reported and skipped so one typo
    cannot stop the others. Nothing is enabled by default and no sample data is ever
    loaded implicitly."""
    sources: list = []
    if settings.source_remotive:
        sources.append(RemotiveSource())
    cfgs, errors = _load_configs()
    for cfg in cfgs:
        try:
            sources.extend(build_sources(_expand(cfg)))
        except Exception as e:  # never log the cfg itself: it may hold headers/tokens
            errors.append(f"{cfg.get('type', 'json_feed')} {cfg.get('name', '')}".strip() + f": {type(e).__name__}: {e}")
    if settings.adzuna_app_id and settings.adzuna_app_key and not any(s.kind == "adzuna" for s in sources):
        sources.append(AdzunaSource())
    unique = {}
    for s in sources:
        unique.setdefault(s.name, s)
    return list(unique.values()), errors


def get_sources() -> list:
    sources, errors = load_sources()
    for e in errors:
        log.error("source config problem: %s", e)
    return sources
