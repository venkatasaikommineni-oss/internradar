"""Fetching raw records from a source, and dry-running a source (no database)."""
import time
from collections import Counter

from ..config import settings
from .normalize import Reject, normalize_record
from .sources.net import redact_text


def fetch_raw(source) -> tuple[list[dict] | None, str | None, int]:
    """-> (records | None, error | None, elapsed_ms). Safe to run in a worker thread:
    it touches the network only, never the database. The error text is secret-free."""
    t0 = time.monotonic()
    try:
        raws, err = list(source.fetch()), None
    except Exception as e:
        raws, err = None, f"{type(e).__name__}: {redact_text(str(e))}"[:500]
    return raws, err, int((time.monotonic() - t0) * 1000)


def preview_source(source, sample: int = 8) -> dict:
    """What WOULD be imported, and why records would be rejected - nothing is stored.
    Use it to check a new source config before enabling it."""
    raws, err, ms = fetch_raw(source)
    out = {
        "source": source.name,
        "kind": getattr(source, "kind", type(source).__name__),
        "complete_listing": bool(getattr(source, "complete_listing", False)),
        "elapsed_ms": ms,
        "error": err,
        "fetched": len(raws or []),
        "accepted": 0,
        "rejected": 0,
        "reject_reasons": {},
        "quality": {},
        "sample": [],
        "sample_rejected": [],
    }
    if raws is None:
        return out
    reasons: Counter = Counter()
    accepted = []
    for raw in raws:
        try:
            accepted.append(normalize_record(raw, source.name, settings.india_only))
        except Reject as e:
            reasons[str(e)] += 1
            if len(out["sample_rejected"]) < sample:
                out["sample_rejected"].append(
                    {"title": raw.get("title"), "location": raw.get("location"), "reason": str(e)}
                )
        except Exception:
            reasons["malformed_record"] += 1
    n = len(accepted)
    out.update(
        accepted=n,
        rejected=sum(reasons.values()),
        reject_reasons=dict(reasons),
        quality={
            "with_description": sum(1 for r in accepted if r["description"]),
            "with_skills": sum(1 for r in accepted if r["skills"]),
            "with_deadline": sum(1 for r in accepted if r["deadline"]),
            "with_stipend": sum(1 for r in accepted if r["stipend_text"]),
            "with_city": sum(1 for r in accepted if r["city"]),
        },
        sample=[
            {k: (v.isoformat() if hasattr(v, "isoformat") else v)
             for k, v in r.items() if k in ("title", "company", "location", "city", "work_type", "skills", "deadline", "application_url")}
            for r in accepted[:sample]
        ],
    )
    return out
