import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import require_admin
from ..models import ImportRun, Internship
from ..schemas import ImportRunOut
from ..services.importer import IMPORT_LOCK, run_many
from ..services.preview import preview_source
from ..services.sources import load_sources
from ..services.status import check_links, refresh_statuses

log = logging.getLogger("internradar.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

OPEN = ("open", "closing_soon")


def _select(sources: list, wanted: str | None) -> list:
    """`wanted` = exact source name, or a kind (e.g. 'greenhouse' = every Greenhouse board)."""
    if wanted is None:
        return sources
    return [s for s in sources if wanted in (s.name, getattr(s, "kind", None)) or s.name.startswith(wanted + ":")]


def _import_in_background(sources: list) -> None:
    db = SessionLocal()
    try:
        run_many(db, sources)
    except Exception:
        log.exception("background import failed")
    finally:
        db.close()


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    """Every configured source with its latest run, plus configuration errors."""
    sources, errors = load_sources()
    last: dict[str, ImportRun] = {}
    for r in db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(2000)):
        last.setdefault(r.source, r)
    return {
        "sources": [
            {
                "name": s.name,
                "kind": getattr(s, "kind", type(s).__name__),
                "complete_listing": bool(getattr(s, "complete_listing", False)),
                "last_run": ImportRunOut.model_validate(last[s.name]) if s.name in last else None,
            }
            for s in sources
        ],
        "config_errors": errors,
    }


@router.post("/sources/test")
def test_source(name: str, sample: int = Query(8, ge=1, le=50)):
    """Dry run: fetch + normalise one source and show what would be imported / rejected and why.
    Nothing is stored. Use it before trusting a new source."""
    sources, _ = load_sources()
    match = _select(sources, name)
    if len(match) != 1:
        raise HTTPException(404 if not match else 400, f"'{name}' matched {len(match)} sources; use an exact name")
    return preview_source(match[0], sample)


@router.post("/import")
def import_now(
    background: BackgroundTasks,
    source: str | None = None,
    wait: bool = Query(False, description="true = run now and return the results; default = run in the background"),
    db: Session = Depends(get_db),
):
    """Run discovery for all configured sources (or one by name / kind). Sources are fetched in parallel."""
    sources = _select(load_sources()[0], source)
    if not sources:
        raise HTTPException(404, "No matching configured source (see GET /api/admin/sources)")
    if IMPORT_LOCK.locked():
        raise HTTPException(409, "A discovery pass is already running; see GET /api/admin/runs")
    if wait:
        return [ImportRunOut.model_validate(r) for r in run_many(db, sources)]
    background.add_task(_import_in_background, sources)
    return {"queued": [s.name for s in sources], "results": "GET /api/admin/runs"}


@router.post("/refresh-status")
def refresh(db: Session = Depends(get_db)):
    return refresh_statuses(db)


@router.post("/check-links")
def links(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    return check_links(db, limit)


@router.get("/runs", response_model=list[ImportRunOut])
def runs(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    return db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(limit)).all()


@router.get("/coverage")
def coverage(db: Session = Depends(get_db)):
    """What the discovery engine has actually found: volume per source / city / work type,
    how many listings are confirmed open, and how complete the records are."""
    I = Internship
    is_open = I.status.in_(OPEN)
    by_status = dict(db.execute(select(I.status, func.count()).group_by(I.status)).all())
    by_basis = dict(db.execute(select(I.status_basis, func.count()).where(is_open).group_by(I.status_basis)).all())
    by_source = [
        {"source": s, "total": t, "open": int(o or 0)}
        for s, t, o in db.execute(
            select(I.source_name, func.count(), func.sum(case((is_open, 1), else_=0)))
            .group_by(I.source_name)
            .order_by(func.count().desc())
        )
    ]
    cities = db.execute(
        select(I.city, func.count()).where(is_open, I.city.is_not(None)).group_by(I.city).order_by(func.count().desc()).limit(15)
    ).all()
    wt = func.coalesce(I.work_type, "unknown")
    by_work_type = dict(db.execute(select(wt, func.count()).where(is_open).group_by(wt)).all())
    total, with_deadline, with_skills, with_stipend, complete = db.execute(
        select(
            func.count(),
            func.sum(case((I.deadline.is_not(None), 1), else_=0)),
            func.sum(case((I.skills_blob != "", 1), else_=0)),
            func.sum(case((I.stipend_text.is_not(None), 1), else_=0)),
            func.sum(case((I.validation_status == "complete", 1), else_=0)),
        ).where(is_open)
    ).one()
    return {
        "open_total": total,
        "by_status": by_status,
        "open_by_evidence": by_basis,  # deadline | source_live | link_check | none
        "by_source": by_source,
        "top_cities": [{"city": c, "open": n} for c, n in cities],
        "by_work_type": by_work_type,
        "open_with": {
            "deadline": int(with_deadline or 0),
            "skills": int(with_skills or 0),
            "stipend": int(with_stipend or 0),
            "complete_record": int(complete or 0),
        },
    }
