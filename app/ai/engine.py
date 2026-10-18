"""Small public facade for the InternRadar AI engine (no DB, no network)."""
from dataclasses import dataclass, field
from typing import Optional

from .matching import DEFAULT_WEIGHTS, prepare_user, rank_internships, score_internship
from .normalize import Reject, normalize_record
from .skills import ROLES, canonical_skill, extract_skills, suggest_roles, suggest_skills
from .status import compute_status

__all__ = ["StudentProfile", "Internship", "normalize_listing", "recommend", "rank", "Reject",
           "extract_skills", "canonical_skill", "suggest_skills", "suggest_roles", "ROLES", "compute_status"]


@dataclass
class StudentProfile:
    skills: list[str] = field(default_factory=list)
    desired_roles: list[str] = field(default_factory=list)
    location: Optional[str] = None
    work_types: list[str] = field(default_factory=list)
    graduation_year: Optional[int] = None


@dataclass
class Internship:
    title: str
    company: str = "Unknown"
    description: str = ""
    skills: list[str] = field(default_factory=list)
    eligibility: Optional[str] = None
    grad_years: list[int] = field(default_factory=list)
    location: Optional[str] = None
    city: Optional[str] = None
    work_type: Optional[str] = None
    deadline: object = None
    status: str = "unverified"


def normalize_listing(raw: dict, source_name: str = "manual") -> dict:
    """Validate and normalise one source listing; raises Reject when invalid."""
    return normalize_record(raw, source_name)


def recommend(profile: StudentProfile, listing: Internship, weights=None) -> dict:
    """Score, matched/missing/implied/related skills, reasons and eligibility for one listing."""
    return score_internship(profile, listing, weights or DEFAULT_WEIGHTS)


def rank(profile: StudentProfile, listings, weights=None, min_score: float = 0.0, include_ineligible: bool = False):
    """Rank many listings for one student. Returns [(listing, result)] best first."""
    ranked, _ = rank_internships(profile, listings, weights or DEFAULT_WEIGHTS,
                                 min_score=min_score, include_ineligible=include_ineligible)
    return ranked
