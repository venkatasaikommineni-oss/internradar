"""Personalized recommendation endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.matching import rank_internships
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Internship, User
from ..schemas import Recommendation, RecommendationPage

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationPage)
def recommend(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_score: float = Query(0, ge=0, le=100),
    include_ineligible: bool = False,
    work_type: str | None = None,
    location: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    has_meaningful_profile = bool(
        (user.skills and len(user.skills) > 0)
        or (user.desired_roles and len(user.desired_roles) > 0)
        or (user.resume_skills and len(user.resume_skills) > 0)
    )
    if not has_meaningful_profile:
        return RecommendationPage(
            total=0,
            items=[],
            notes=["Complete your profile or upload a resume to get personalized recommendations."],
        )

    notes = []
    if not user.email_verified:
        notes.append("Verify your email for the best experience.")
    if not user.desired_roles:
        notes.append("Select desired roles in your profile for better role-based matching.")
    elif not user.skills and not user.resume_skills:
        notes.append("Add skills or upload a resume to improve skill matching.")

    cands_q = select(Internship).where(Internship.status != "expired").order_by(Internship.collected_at.desc()).limit(settings.recommend_candidate_cap)
    if work_type:
        cands_q = cands_q.where(Internship.work_type == work_type)
    if location:
        cands_q = cands_q.where(Internship.city.icontains(location, autoescape=True))

    candidates = db.scalars(cands_q).all()

    ranked, hidden = rank_internships(
        user, candidates, settings.weights,
        min_score=min_score, include_ineligible=include_ineligible,
    )
    if hidden:
        notes.append(f"{hidden} listing(s) hidden because you do not meet a stated eligibility requirement.")

    page = ranked[offset: offset + limit]
    items = []
    for it, res in page:
        rec = Recommendation(
            internship=it,
            resume_boost=bool(res.get("resume_boost")),
            **{k: v for k, v in res.items() if k != "resume_boost"},
        )
        items.append(rec)
    return RecommendationPage(total=len(ranked), items=items, notes=notes)
