"""Discovery pipeline: fetch (parallel, network-bound) -> normalize -> validate ->
dedupe -> store (sequential, one writer) -> status -> log.

Fetching dominates the run time, so all sources are fetched concurrently in worker
threads while the main thread writes finished sources to the database one at a time
(SQLite allows a single writer; this also keeps each source's import atomic)."""
import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import ImportRun, Internship, utcnow
from .normalize import Reject, normalize_record
from .preview import fetch_raw
from .sources import get_sources
from .status import compute_status, refresh_statuses

log = logging.getLogger("internradar.importer")

IMPORT_LOCK = threading.Lock()  # one discovery pass at a time (scheduler vs. manual trigger)

# fields refreshed from the source on re-import (never overwritten with empty values)
_UPDATABLE = [
    "title", "company", "company_website", "description", "skills", "skills_blob", "eligibility",
    "grad_years", "location", "city", "work_type", "stipend_text", "stipend_min", "stipend_max",
    "duration_text", "duration_months", "deadline", "application_url", "apply_url_key",
    "source_url", "fingerprint", "validation_status",
]
# fields a *different* source may fill in on a cross-source duplicate
_FILLABLE = ["description", "eligibility", "deadline", "stipend_text", "stipend_min", "stipend_max",
             "duration_text", "duration_months", "company_website", "work_type", "city"]


def _empty(v) -> bool:
    return v is None or v == [] or v == ""


def _load_index(db: Session, source_name: str):
    """Two queries: id lookups across ALL sources for dedup, and this source's own rows in
    full (they are the ones that get updated) - so matching needs no per-record SELECT."""
    by_fp, by_url = {}, {}
    for r in db.execute(select(Internship.id, Internship.fingerprint, Internship.apply_url_key)):
        by_fp.setdefault(r.fingerprint, r.id)
        by_url.setdefault(r.apply_url_key, r.id)
    own = {r.id: r for r in db.scalars(select(Internship).where(Internship.source_name == source_name))}
    by_ext = {r.external_id: r for r in own.values() if r.external_id}
    return by_fp, by_url, own, by_ext


def _ingest(db: Session, source, raws: list[dict], c: Counter, reasons: Counter) -> int:
    """Store one source's records. Returns how many listings were closed because the source dropped them."""
    live = bool(getattr(source, "complete_listing", False))
    by_fp, by_url, own, by_ext = _load_index(db, source.name)
    now = utcnow()

    def resolve(ref):
        if ref is None or isinstance(ref, Internship):
            return ref
        return own.get(ref) or db.get(Internship, ref)

    for raw in raws:
        c["fetched"] += 1
        try:
            rec = normalize_record(raw, source.name, settings.india_only)
        except Reject as e:
            c["rejected"] += 1
            reasons[str(e)] += 1
            continue
        except Exception:  # malformed record must not kill the run
            c["rejected"] += 1
            c["malformed"] += 1
            reasons["malformed_record"] += 1
            continue

        ext = rec["external_id"]
        row, dup = by_ext.get(ext) if ext else None, None
        if row is None:
            cand = resolve(by_fp.get(rec["fingerprint"]) or by_url.get(rec["apply_url_key"]))
            if cand is not None:
                if cand.source_name != source.name:
                    dup = cand  # same opportunity seen via another source
                elif ext and cand.external_id and cand.external_id != ext:
                    pass  # a distinct posting of the same source (e.g. a re-posted requisition) -> new row
                else:
                    row = cand

        if row is None and dup is None:
            row = Internship(**rec, collected_at=now, updated_at=now, last_seen_at=now)
            row.status, row.status_basis = compute_status(row.deadline, None, now, live)
            if live:
                row.last_checked_at = now  # the company board itself is the confirmation; no link probe needed
            db.add(row)
            c["created"] += 1
            if ext:
                by_ext[ext] = row
            by_fp.setdefault(rec["fingerprint"], row)
            by_url.setdefault(rec["apply_url_key"], row)
        elif row is not None:  # same source: refresh the stored copy
            row.last_seen_at = now
            changed = False
            for f in _UPDATABLE:
                new = rec[f]
                if not _empty(new) and getattr(row, f) != new:
                    setattr(row, f, new)
                    changed = True
            if live:
                row.last_checked_at = now
                if row.link_ok is False:  # the board still lists it, so trust the board over an old probe
                    row.link_ok = None
            row.status, row.status_basis = compute_status(row.deadline, row.link_ok, now, live)
            if changed:
                row.updated_at = now
                c["updated"] += 1
            else:
                c["unchanged"] += 1
        else:  # cross-source duplicate: keep the original, fill gaps only
            for f in _FILLABLE:
                if _empty(getattr(dup, f)) and not _empty(rec[f]):
                    setattr(dup, f, rec[f])
            dup.last_seen_at = now  # still available somewhere
            if dup.status_basis == "source_sync":
                dup.status, dup.status_basis = compute_status(dup.deadline, dup.link_ok, now, False)
            c["duplicates"] += 1

    # Confirmed source availability: a source that publishes its COMPLETE list of open roles
    # has taken down whatever it stored earlier but no longer lists. (Guard: an empty or
    # all-malformed response must never be read as "everything was closed".)
    closed = 0
    if live and c["fetched"] > c["malformed"]:
        db.flush()  # autoflush is off; last_seen_at must be in the DB before the bulk UPDATE
        closed = db.execute(
            update(Internship)
            .where(
                Internship.source_name == source.name,
                Internship.last_seen_at < now,
                Internship.status_basis != "source_sync",
            )
            .values(status="expired", status_basis="source_sync")
        ).rowcount or 0
        if closed:
            log.info("%s: %s listing(s) no longer on the source -> closed", source.name, closed)
    return closed


def run_import(db: Session, source, *, prefetched=None, refresh: bool = True) -> ImportRun:
    """Import one source. `prefetched` = (records, error, elapsed_ms) from fetch_raw()."""
    t0 = time.monotonic()
    run = ImportRun(source=source.name, status="running", started_at=utcnow())
    db.add(run)
    db.commit()

    raws, error, fetch_ms = prefetched if prefetched is not None else fetch_raw(source)
    c, reasons, closed = Counter(), Counter(), 0
    if error:
        log.warning("source %s failed: %s", source.name, error)
    else:
        try:
            closed = _ingest(db, source, raws, c, reasons)
            db.commit()
            if refresh:
                refresh_statuses(db)
        except Exception as e:  # database problem: nothing of this batch is kept
            db.rollback()
            error = f"{type(e).__name__}: {e}"[:500]
            log.exception("import failed for source %s", source.name)
            c, reasons, closed = Counter(fetched=len(raws)), Counter(), 0

    run = db.get(ImportRun, run.id)
    run.status = "failed" if error else "success"
    run.error = error
    run.finished_at = utcnow()
    run.fetched, run.created, run.updated = c["fetched"], c["created"], c["updated"]
    run.unchanged, run.duplicates, run.rejected = c["unchanged"], c["duplicates"], c["rejected"]
    run.reject_reasons = dict(reasons)
    run.closed = closed
    run.duration_ms = fetch_ms + int((time.monotonic() - t0) * 1000)
    db.commit()
    return run


def run_many(db: Session, sources: list, workers: int | None = None) -> list[ImportRun]:
    """Fetch every source in parallel, store each as soon as it finishes, refresh statuses once.
    Returns [] if another discovery pass is already running."""
    if not sources:
        return []
    if not IMPORT_LOCK.acquire(blocking=False):
        log.warning("a discovery pass is already running; skipping")
        return []
    try:
        workers = max(1, min(workers or settings.discovery_workers, len(sources)))
        runs = []
        with ThreadPoolExecutor(workers, thread_name_prefix="fetch") as pool:
            futures = {pool.submit(fetch_raw, s): s for s in sources}
            for fut in as_completed(futures):
                runs.append(run_import(db, futures[fut], prefetched=fut.result(), refresh=False))
        refresh_statuses(db)
        return runs
    finally:
        IMPORT_LOCK.release()


def run_all_sources(db: Session) -> list[ImportRun]:
    return run_many(db, get_sources())
