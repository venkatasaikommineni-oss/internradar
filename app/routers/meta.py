from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImportRun, Internship
from ..ai.geo import suggest_cities
from ..ai.skills import suggest_roles, suggest_skills, suggest_specializations, SPECIALIZATIONS, ROLES
from ..services.geo import suggest_cities as svc_suggest_cities

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta/skills")
def skills(q: str = "", limit: int = Query(20, ge=1, le=100)):
    return suggest_skills(q, limit)


@router.get("/meta/locations")
def locations(q: str = "", limit: int = Query(15, ge=1, le=100)):
    return suggest_cities(q, limit)


@router.get("/meta/roles")
def roles(q: str = "", limit: int = Query(20, ge=1, le=100)):
    return suggest_roles(q, limit)


@router.get("/meta/specializations")
def specializations(q: str = "", limit: int = Query(20, ge=1, le=100)):
    return suggest_specializations(q, limit)


@router.get("/meta/all-roles")
def all_roles():
    return ROLES


@router.get("/meta/all-specializations")
def all_specializations():
    return SPECIALIZATIONS


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    """Public health snapshot: listing counts and the latest import per source."""
    by_status = dict(db.execute(select(Internship.status, func.count()).group_by(Internship.status)).all())
    latest = {}
    for run in db.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(50)):
        latest.setdefault(run.source, {
            "status": run.status, "finished_at": run.finished_at, "error": run.error,
            "fetched": run.fetched, "created": run.created,
        })
    total_open = sum(v for k, v in by_status.items() if k in ("open", "closing_soon"))
    return {"internships": by_status, "total_open": total_open, "sources": latest}
