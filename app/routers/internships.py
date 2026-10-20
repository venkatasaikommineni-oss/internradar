import logging
import threading
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_, select
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

_refresh_lock = threading.Lock()
_refresh_state = {
    "is_running": False,
    "last_run_at": None,
    "last_status": "idle",
    "last_message": "Ready to refresh",
}


def _import_in_background(sources: list) -> None:
    db = SessionLocal()
    try:
        run_many(db, sources)
        with _refresh_lock:
            _refresh_state["last_run_at"] = datetime.now(timezone.utc).isoformat()
            _refresh_state["last_status"] = "success"
            _refresh_state["last_message"] = f"Successfully checked {len(sources)} live sources."
    except Exception as e:
        log.exception("background discovery refresh failed")
        with _refresh_lock:
            _refresh_state["last_status"] = "error"
            _refresh_state["last_message"] = f"Could not complete fresh discovery: {e}"
    finally:
        with _refresh_lock:
            _refresh_state["is_running"] = False
        db.close()


@router.post("/refresh")
def refresh_internships(background_tasks: BackgroundTasks):
    """Trigger background discovery pass to refresh and ingest newly opened internships."""
    with _refresh_lock:
        if _refresh_state["is_running"]:
            return {
                "status": "running",
                "message": "Discovery is currently in progress. Showing latest available listings.",
                "last_run_at": _refresh_state["last_run_at"],
            }
        # 60 second cooldown to avoid spamming external employer APIs
        if _refresh_state["last_run_at"]:
            try:
                last_dt = datetime.fromisoformat(_refresh_state["last_run_at"])
                if (datetime.now(timezone.utc) - last_dt).total_seconds() < 60:
                    return {
                        "status": "cooldown",
                        "message": "Discovery refreshed recently. Showing latest stored listings.",
                        "last_run_at": _refresh_state["last_run_at"],
                    }
            except Exception:
                pass

        _refresh_state["is_running"] = True
        _refresh_state["last_status"] = "running"
        _refresh_state["last_message"] = "Discovery in progress across live sources..."

    sources = get_sources()
    background_tasks.add_task(_import_in_background, sources)
    return {
        "status": "started",
        "message": f"Discovery refresh started across {len(sources)} sources.",
        "last_run_at": _refresh_state["last_run_at"],
    }


@router.get("/refresh-status")
def get_refresh_status():
    """Check the status and last run timestamp of the background discovery job."""
    with _refresh_lock:
        return {
            "status": _refresh_state["last_status"],
            "last_status": _refresh_state["last_status"],
            "is_running": _refresh_state["is_running"],
            "last_run_at": _refresh_state["last_run_at"],
            "last_message": _refresh_state["last_message"],
        }


SOFTWARE_TITLE_PATTERNS = [
    "%software%", "%developer%", "%engineer%", "%engineering%", "%frontend%", "%front-end%",
    "%backend%", "%back-end%", "%full-stack%", "%fullstack%", "%sde%", "%sdet%",
    "%mobile%", "%android%", "%ios%", "%flutter%", "%react%", "%node%", "%python%",
    "%java%", "%ai%", "%ml%", "%machine learning%", "%data science%", "%data engineer%",
    "%data analyst%", "%devops%", "%cloud%", "%sre%", "%qa%", "%testing%",
    "%cybersecurity%", "%security%", "%embedded%", "%iot%", "%systems%", "%solutions%"
]

CATEGORY_PATTERNS = {
    "software": ["%software%", "%developer%", "%engineer%", "%sde%", "%programmer%"],
    "frontend": ["%frontend%", "%front-end%", "%react%", "%vue%", "%angular%", "%web dev%"],
    "backend": ["%backend%", "%back-end%", "%api%", "%node%", "%django%", "%spring%", "%golang%"],
    "fullstack": ["%full-stack%", "%fullstack%", "%mern%"],
    "data_ai": ["%data%", "%machine learning%", "%ai%", "%deep learning%", "%analytics%", "%nlp%"],
    "cloud_devops": ["%cloud%", "%devops%", "%sre%", "%kubernetes%", "%aws%", "%azure%", "%infrastructure%"],
    "qa": ["%qa%", "%testing%", "%test automation%", "%sdet%", "%quality%"],
    "cybersecurity": ["%security%", "%cyber%", "%infosec%", "%penetration%"],
    "design": ["%design%", "%ui%", "%ux%", "%figma%", "%visual%"],
    "marketing": ["%marketing%", "%growth%", "%seo%", "%content%"],
}


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
    category: str | None = Query(None, description="filter by functional role category"),
    include_expired: bool = False,
    sort: Literal["newest", "deadline", "stipend"] = "newest",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    I = Internship
    conds = []

    q_clean = q.strip() if isinstance(q, str) and q.strip() else None
    if q_clean:
        conds.append(
            I.title.icontains(q_clean, autoescape=True)
            | I.company.icontains(q_clean, autoescape=True)
            | I.description.icontains(q_clean, autoescape=True)
        )

    if skills:
        wanted = []
        for s in skills.split(","):
            if s.strip():
                wanted.append((canonical_skill(s) or s.strip()).lower())
        clauses = [I.skills_blob.contains(f"|{s}|", autoescape=True) for s in wanted]
        if clauses:
            conds.append(and_(*clauses) if skills_match == "all" else or_(*clauses))

    loc_clean = location.strip() if isinstance(location, str) and location.strip() else None
    if loc_clean:
        conds.append(I.city.icontains(loc_clean, autoescape=True) | I.location.icontains(loc_clean, autoescape=True))

    if work_type:
        conds.append(I.work_type == work_type)

    if min_stipend is not None:
        conds.append(I.stipend_max >= min_stipend)

    if deadline_before:
        conds.append(I.deadline <= deadline_before)

    comp_clean = company.strip() if isinstance(company, str) and company.strip() else None
    if comp_clean:
        conds.append(I.company.icontains(comp_clean, autoescape=True))

    if status:
        conds.append(I.status == status)
    elif not include_expired:
        conds.append(I.status != "expired")

    if category and category.lower() in CATEGORY_PATTERNS:
        pats = CATEGORY_PATTERNS[category.lower()]
        conds.append(or_(*[I.title.ilike(p) for p in pats]))

    total = db.scalar(select(func.count()).select_from(I).where(*conds)) or 0

    # Software / Engineering prioritization flag for discovery ranking (~70% software emphasis)
    is_software = or_(*[I.title.ilike(p) for p in SOFTWARE_TITLE_PATTERNS])

    order = {
        "newest": [case((is_software, 1), else_=0).desc(), I.collected_at.desc(), I.id.desc()],
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
