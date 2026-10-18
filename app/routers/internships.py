import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Internship
from ..schemas import InternshipOut, InternshipPage
from ..services.importer import run_many
from ..services.skills import canonical_skill
from ..services.sources import get_sources

log = logging.getLogger("internradar.internships")
router = APIRouter(prefix="/api/internships", tags=["internships"])

Status = Literal["open", "closing_soon", "expired", "unverified"]


def _import_in_background(sources: list) -> None:
    db = SessionLocal()
    try:
        run_many(db, sources)
    except Exception:
        log.exception("background discovery refresh failed")
    finally:
        db.close()


@router.post("/refresh")
def refresh_internships(background_tasks: BackgroundTasks):
    """Trigger background discovery pass to refresh and ingest newly opened internships."""
    sources = get_sources()
    background_tasks.add_task(_import_in_background, sources)
    return {"message": f"Discovery refresh started across {len(sources)} sources."}



@router.get("", response_model=InternshipPage)
def search_internships(
    q: str | None = Query(None, description="keyword in title, company or description"),
    skills: str | None = Query(None, description="comma-separated skills"),
    skills_match: Literal["any", "all"] = "all",
    location: str | None = None,
    work_type: Literal["remote", "hybrid", "onsite"] | None = None,
    min_stipend: int | None = Query(None, ge=0, description="INR / month"),
    deadline_before: datetime | None = None,
    company: str | None = None,
    status: Status | None = None,
    include_expired: bool = False,
    sort: Literal["newest", "deadline", "stipend"] = "newest",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    I = Internship
    conds = []
    if q:
        conds.append(I.title.icontains(q, autoescape=True) | I.company.icontains(q, autoescape=True)
                     | I.description.icontains(q, autoescape=True))
    if skills:
        wanted = []
        for s in skills.split(","):
            if s.strip():
                wanted.append((canonical_skill(s) or s.strip()).lower())
        clauses = [I.skills_blob.contains(f"|{s}|", autoescape=True) for s in wanted]
        if clauses:
            conds.append(and_(*clauses) if skills_match == "all" else or_(*clauses))
    if location:
        conds.append(I.city.icontains(location, autoescape=True) | I.location.icontains(location, autoescape=True))
    if work_type:
        conds.append(I.work_type == work_type)
    if min_stipend is not None:
        conds.append(I.stipend_max >= min_stipend)
    if deadline_before:
        conds.append(I.deadline <= deadline_before)
    if company:
        conds.append(I.company.icontains(company, autoescape=True))
    if status:
        conds.append(I.status == status)
    elif not include_expired:
        conds.append(I.status != "expired")

    total = db.scalar(select(func.count()).select_from(I).where(*conds)) or 0

    order = {
        "newest": [I.collected_at.desc(), I.id.desc()],
        "deadline": [I.deadline.is_(None), I.deadline.asc(), I.id.desc()],
        "stipend": [I.stipend_max.is_(None), I.stipend_max.desc(), I.id.desc()],
    }[sort]
    rows = db.scalars(select(I).where(*conds).order_by(*order).limit(limit).offset(offset)).all()
    return InternshipPage(total=total, limit=limit, offset=offset, items=rows)


@router.get("/{internship_id}", response_model=InternshipOut)
def get_internship(internship_id: int, db: Session = Depends(get_db)):
    row = db.get(Internship, internship_id)
    if not row:
        raise HTTPException(404, "Internship not found")
    return row
