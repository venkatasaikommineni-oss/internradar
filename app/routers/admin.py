import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..deps import AdminPrincipal, require_admin, require_admin_access
from ..models import ImportRun, Internship, SavedInternship, User, UserActivity, UserConnection
from ..schemas import AdminUserDetail, AdminUserListItem, AdminUserPage, ImportRunOut
from ..services.importer import IMPORT_LOCK, run_many
from ..services.preview import preview_source
from ..services.sources import load_sources
from ..services.status import check_links, refresh_statuses
from .users import get_safe_resume_path

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


# ── user management ───────────────────────────────────────────────────────────
def _compute_missing_fields(u: User) -> list[str]:
    missing = []
    if not (u.full_name and u.full_name.strip()):
        missing.append("full_name")
    if not (u.college and u.college.strip()):
        missing.append("college")
    if not (u.degree and u.degree.strip()):
        missing.append("degree")
    if not u.graduation_year:
        missing.append("graduation_year")
    if not (u.location and u.location.strip()):
        missing.append("location")
    if not (u.skills and len(u.skills) > 0):
        missing.append("skills")
    if not (u.desired_roles and len(u.desired_roles) > 0):
        missing.append("desired_roles")
    if not (u.work_types and len(u.work_types) > 0):
        missing.append("work_types")
    return missing


def _build_list_item(u: User) -> AdminUserListItem:
    missing = _compute_missing_fields(u)
    return AdminUserListItem(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        college=u.college,
        degree=u.degree,
        graduation_year=u.graduation_year,
        location=u.location,
        skills=u.skills or [],
        desired_roles=u.desired_roles or [],
        work_types=u.work_types or [],
        is_admin=bool(u.is_admin),
        is_active=bool(u.is_active),
        is_onboarded=bool(u.is_onboarded),
        has_resume=bool(u.resume_path),
        resume_filename=u.resume_filename,
        resume_size_bytes=u.resume_size_bytes,
        resume_uploaded_at=u.resume_uploaded_at,
        missing_fields=missing,
        created_at=u.created_at,
        updated_at=u.updated_at,
        last_login=u.last_login,
    )


@router.get("/users", response_model=AdminUserPage)
def list_users_admin(
    q: str | None = Query(None, description="Search by full name, email, or college"),
    skills: str | None = Query(None, description="Filter by comma-separated skill list"),
    grad_year: int | None = Query(None, description="Filter by graduation year"),
    completion: str = Query("all", description="Filter by completeness: all | complete | incomplete"),
    resume: str = Query("all", description="Filter by resume status: all | with_resume | without_resume"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: AdminPrincipal = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Admin-only: list all registered users with filter, search, profile completeness, and resume status."""
    log.info(
        "AUDIT [Admin: %s] list_users (q='%s', skills='%s', grad_year=%s, completion=%s, resume=%s, limit=%d, offset=%d)",
        admin.identifier,
        q or "",
        skills or "",
        grad_year,
        completion,
        resume,
        limit,
        offset,
    )

    query = select(User)
    conds = []

    if q:
        query_pattern = f"%{q.strip()}%"
        conds.append(
            or_(
                User.full_name.ilike(query_pattern),
                User.email.ilike(query_pattern),
                User.college.ilike(query_pattern),
            )
        )

    if grad_year:
        conds.append(User.graduation_year == grad_year)

    if resume == "with_resume":
        conds.append(User.resume_path.is_not(None))
    elif resume == "without_resume":
        conds.append(User.resume_path.is_(None))

    if conds:
        query = query.where(*conds)

    all_matched = db.scalars(query.order_by(User.id.desc())).all()

    # In-memory filtering for skills and profile completeness
    filtered: list[User] = []
    wanted_skills = {s.strip().lower() for s in skills.split(",") if s.strip()} if skills else set()

    for u in all_matched:
        if wanted_skills:
            user_skills = {s.lower() for s in (u.skills or [])}
            if not (wanted_skills & user_skills):
                continue

        missing = _compute_missing_fields(u)
        is_complete = len(missing) == 0
        if completion == "complete" and not is_complete:
            continue
        if completion == "incomplete" and is_complete:
            continue

        filtered.append(u)

    total = len(filtered)
    page_users = filtered[offset : offset + limit]
    items = [_build_list_item(u) for u in page_users]

    return AdminUserPage(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail_admin(
    user_id: int,
    admin: AdminPrincipal = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Admin-only: inspect comprehensive user profile, academic history, preferences, and activity counts."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    log.info("AUDIT [Admin: %s] view_user_detail user_id=%d (%s)", admin.identifier, user.id, user.email)

    # Activity and connection counts
    saved_count = db.scalar(select(func.count()).select_from(SavedInternship).where(SavedInternship.user_id == user.id)) or 0
    activity_count = db.scalar(select(func.count()).select_from(UserActivity).where(UserActivity.user_id == user.id)) or 0
    connections_count = db.scalar(
        select(func.count()).select_from(UserConnection).where(
            or_(UserConnection.requester_id == user.id, UserConnection.addressee_id == user.id)
        )
    ) or 0

    base_item = _build_list_item(user)
    return AdminUserDetail(
        **base_item.model_dump(),
        mobile=user.mobile,
        gender=user.gender,
        branch=user.branch,
        cgpa=user.cgpa,
        bio=user.bio,
        linkedin_url=user.linkedin_url,
        github_url=user.github_url,
        portfolio_url=user.portfolio_url,
        resume_content_type=user.resume_content_type,
        resume_skills=user.resume_skills or [],
        email_verified=bool(user.email_verified),
        saved_count=saved_count,
        activity_count=activity_count,
        connections_count=connections_count,
    )


@router.get("/users/{user_id}/resume")
def download_user_resume_admin(
    user_id: int,
    download: bool = Query(False, description="Whether to trigger file download"),
    admin: AdminPrincipal = Depends(require_admin_access),
    db: Session = Depends(get_db),
):
    """Admin-only: secure preview or download of user uploaded resume."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    if not user.resume_path:
        raise HTTPException(404, "User has not uploaded a resume")

    safe_path = get_safe_resume_path(user.resume_path)
    filename = user.resume_filename or os.path.basename(safe_path)
    disposition = "attachment" if download else "inline"

    log.info(
        "AUDIT [Admin: %s] download_resume user_id=%d (target=%s, file=%s, disposition=%s)",
        admin.identifier,
        user.id,
        user.email,
        filename,
        disposition,
    )

    return FileResponse(
        safe_path,
        media_type=user.resume_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )
