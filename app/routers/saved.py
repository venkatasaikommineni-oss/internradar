"""Saved internships (bookmarks) + activity / history tracking."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Internship, SavedInternship, User, UserActivity, utcnow
from ..schemas import ActivityOut, ActivityPage, SavedOut

router = APIRouter(tags=["saved & activity"])


# ── saved / bookmarks ─────────────────────────────────────────────────────────
saved_router = APIRouter(prefix="/api/saved")


@saved_router.get("", response_model=list[SavedOut])
def list_saved(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(SavedInternship.saved_at, SavedInternship.notes, Internship)
        .join(Internship, Internship.id == SavedInternship.internship_id)
        .where(SavedInternship.user_id == user.id)
        .order_by(SavedInternship.saved_at.desc())
    ).all()
    return [SavedOut(saved_at=r.saved_at, notes=r.notes, internship=r.Internship) for r in rows]


@saved_router.put("/{internship_id}", status_code=204)
def save(
    internship_id: int,
    notes: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bookmark/save an internship. Idempotent."""
    if not db.get(Internship, internship_id):
        raise HTTPException(404, "Internship not found")
    existing = db.scalar(
        select(SavedInternship).where(
            SavedInternship.user_id == user.id,
            SavedInternship.internship_id == internship_id,
        )
    )
    if existing:
        if notes is not None:
            existing.notes = notes
            db.commit()
    else:
        db.add(SavedInternship(user_id=user.id, internship_id=internship_id, notes=notes))
        # Log activity
        db.add(UserActivity(user_id=user.id, internship_id=internship_id, action="bookmarked"))
        # Increment listing counter
        listing = db.get(Internship, internship_id)
        if listing:
            listing.view_count = (listing.view_count or 0) + 1
        db.commit()
    return Response(status_code=204)


@saved_router.delete("/{internship_id}", status_code=204)
def unsave(
    internship_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.execute(
        delete(SavedInternship).where(
            SavedInternship.user_id == user.id,
            SavedInternship.internship_id == internship_id,
        )
    )
    db.add(UserActivity(user_id=user.id, internship_id=internship_id, action="unbookmarked"))
    db.commit()
    return Response(status_code=204)


router.include_router(saved_router)


# ── activity / history ────────────────────────────────────────────────────────
activity_router = APIRouter(prefix="/api/activity")


@activity_router.post("/view/{internship_id}", status_code=204)
def track_view(
    internship_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record that the user viewed an internship detail page."""
    if not db.get(Internship, internship_id):
        raise HTTPException(404, "Internship not found")
    db.add(UserActivity(user_id=user.id, internship_id=internship_id, action="viewed"))
    listing = db.get(Internship, internship_id)
    if listing:
        listing.view_count = (listing.view_count or 0) + 1
    db.commit()
    return Response(status_code=204)


@activity_router.post("/apply/{internship_id}", status_code=204)
def track_apply_click(
    internship_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record that the user clicked Apply (before redirect to original site)."""
    if not db.get(Internship, internship_id):
        raise HTTPException(404, "Internship not found")
    db.add(UserActivity(user_id=user.id, internship_id=internship_id, action="apply_clicked"))
    listing = db.get(Internship, internship_id)
    if listing:
        listing.apply_click_count = (listing.apply_click_count or 0) + 1
    db.commit()
    return Response(status_code=204)


@activity_router.get("", response_model=ActivityPage)
def get_activity(
    action: str | None = Query(None, description="Filter: viewed|apply_clicked|bookmarked"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Full activity history for the current user."""
    conds = [UserActivity.user_id == user.id]
    if action:
        conds.append(UserActivity.action == action)

    total = db.scalar(select(func.count()).select_from(UserActivity).where(*conds)) or 0
    rows = db.execute(
        select(UserActivity, Internship)
        .join(Internship, Internship.id == UserActivity.internship_id, isouter=True)
        .where(*conds)
        .order_by(UserActivity.timestamp.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = []
    for act, intern in rows:
        item = ActivityOut(
            id=act.id,
            internship_id=act.internship_id,
            action=act.action,
            detail=act.detail,
            timestamp=act.timestamp,
            internship=intern,
        )
        items.append(item)
    return ActivityPage(total=total, items=items)


@activity_router.get("/applied", response_model=ActivityPage)
def get_applied(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Internships the user clicked 'Apply' on (= apply_clicked activities)."""
    conds = [UserActivity.user_id == user.id, UserActivity.action == "apply_clicked"]
    total = db.scalar(select(func.count()).select_from(UserActivity).where(*conds)) or 0
    rows = db.execute(
        select(UserActivity, Internship)
        .join(Internship, Internship.id == UserActivity.internship_id, isouter=True)
        .where(*conds)
        .order_by(UserActivity.timestamp.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        ActivityOut(id=a.id, internship_id=a.internship_id, action=a.action,
                    detail=a.detail, timestamp=a.timestamp, internship=i)
        for a, i in rows
    ]
    return ActivityPage(total=total, items=items)


router.include_router(activity_router)
