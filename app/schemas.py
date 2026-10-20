from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, computed_field, field_validator, model_validator, validator

WorkType = Literal["remote", "hybrid", "onsite"]
Gender = Literal["male", "female", "non_binary", "prefer_not_to_say"]
ConnectionStatus = Literal["pending", "accepted", "rejected", "blocked"]


# ── internships ──────────────────────────────────────────────────────────────
class InternshipCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company: str
    company_website: str | None = None
    description: str | None = Field(default=None, exclude=True)
    skills: list[str] = []
    eligibility: str | None = None
    grad_years: list[int] = []
    location: str | None = None
    city: str | None = None
    work_type: str | None = None
    stipend_text: str | None = None
    stipend_min: int | None = None
    stipend_max: int | None = None
    duration_text: str | None = None
    duration_months: float | None = None
    deadline: datetime | None = None
    application_url: str
    source_name: str
    source_url: str | None = None
    status: str
    status_basis: str
    link_ok: bool | None = None
    last_checked_at: datetime | None = None
    collected_at: datetime
    updated_at: datetime
    validation_status: str
    view_count: int = 0
    apply_click_count: int = 0

    @computed_field
    @property
    def snippet(self) -> str | None:
        d = (self.description or "").strip()
        return (d[:280].rstrip() + "…") if len(d) > 280 else (d or None)

    @computed_field
    @property
    def missing_fields(self) -> list[str]:
        out = []
        if not self.deadline:
            out.append("deadline")
        if not self.stipend_text:
            out.append("stipend")
        if not self.duration_text:
            out.append("duration")
        if not self.eligibility and not self.grad_years:
            out.append("eligibility")
        if not self.skills:
            out.append("skills")
        return out

    @computed_field
    @property
    def days_until_deadline(self) -> int | None:
        if not self.deadline:
            return None
        from datetime import timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        diff = (self.deadline - now).days
        return diff


class InternshipOut(InternshipCard):
    description: str | None = None


class InternshipPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[InternshipCard]


# ── auth ─────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self





class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    is_onboarded: bool
    is_admin: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ── profile ───────────────────────────────────────────────────────────────────
class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    gender: Gender | None = None
    location: str | None = None
    college: str | None = Field(default=None, max_length=200)
    mobile: str | None = Field(default=None, max_length=20)
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    bio: str | None = Field(default=None, max_length=500)
    skills: list[str] | None = None
    specializations: list[str] | None = None
    desired_roles: list[str] | None = None
    work_types: list[WorkType] | None = None
    graduation_year: int | None = Field(default=None, ge=2020, le=2035)
    degree: str | None = Field(default=None, max_length=100)
    branch: str | None = Field(default=None, max_length=100)
    cgpa: float | None = Field(default=None, ge=0.0, le=10.0)
    notify_new_matches: bool | None = None
    notify_deadline: bool | None = None

    @field_validator("full_name", "college", "degree", "location", mode="before")
    @classmethod
    def _validate_required_text(cls, v: str | None, info):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                field_name = info.field_name.replace("_", " ").title()
                raise ValueError(f"{field_name} cannot be empty or whitespace only")
            return s
        return v

    @field_validator("skills", "desired_roles", "work_types", mode="before")
    @classmethod
    def _validate_required_list(cls, v: list | None, info):
        if v is None:
            return None
        if isinstance(v, list):
            cleaned = [str(x).strip() for x in v if str(x).strip()]
            if not cleaned:
                field_name = info.field_name.replace("_", " ").title()
                raise ValueError(f"At least one {field_name.lower()} is required")
            return cleaned
        return v

    @field_validator("linkedin_url", "github_url", "portfolio_url", mode="before")
    @classmethod
    def _validate_optional_urls(cls, v: str | None):
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            if not (s.startswith("http://") or s.startswith("https://")):
                s = f"https://{s}"
            return s
        return v

    @field_validator("mobile", mode="before")
    @classmethod
    def _validate_mobile(cls, v: str | None):
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None = None
    email: str | None = None
    gender: str | None = None
    location: str | None = None
    college: str | None = None
    mobile: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    bio: str | None = None
    profile_photo: str | None = None
    skills: list[str] = []
    specializations: list[str] = []
    desired_roles: list[str] = []
    work_types: list[str] = []
    graduation_year: int | None = None
    degree: str | None = None
    branch: str | None = None
    cgpa: float | None = None
    email_verified: bool = False
    is_onboarded: bool = False
    is_admin: bool = False
    resume_path: str | None = None
    resume_filename: str | None = None
    resume_content_type: str | None = None
    resume_size_bytes: int | None = None
    resume_uploaded_at: datetime | None = None
    resume_skills: list[str] = []
    notify_new_matches: bool = True
    notify_deadline: bool = True
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None


class PublicUserOut(BaseModel):
    """Public profile visible to connected users."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None = None
    location: str | None = None
    college: str | None = None
    bio: str | None = None
    profile_photo: str | None = None
    skills: list[str] = []
    desired_roles: list[str] = []
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    graduation_year: int | None = None
    degree: str | None = None
    branch: str | None = None
    created_at: datetime


# ── recommendations ───────────────────────────────────────────────────────────
class EligibilityOut(BaseModel):
    status: Literal["eligible", "not_eligible", "unknown"]
    detail: str
    requirements: str | None = None


class Recommendation(BaseModel):
    internship: InternshipCard
    score: float
    breakdown: dict[str, float | None]
    matched_skills: list[str]
    missing_skills: list[str]
    reasons: list[str]
    match_level: Literal["strong", "good", "partial", "weak"] = "weak"
    confidence: Literal["high", "medium", "low"] = "low"
    matched_role: str | None = None
    implied_skills: list[dict] = []
    related_skills: list[dict] = []
    skills_inferred: bool = False
    role_skill_gaps: list[str] = []
    resume_boost: bool = False  # whether resume text contributed to the score
    eligibility: EligibilityOut


class RecommendationPage(BaseModel):
    total: int
    items: list[Recommendation]
    notes: list[str] = []


# ── saved ─────────────────────────────────────────────────────────────────────
class SavedOut(BaseModel):
    saved_at: datetime
    notes: str | None = None
    internship: InternshipCard


# ── activity ──────────────────────────────────────────────────────────────────
class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    internship_id: int
    action: str
    detail: str | None = None
    timestamp: datetime
    internship: InternshipCard | None = None


class ActivityPage(BaseModel):
    total: int
    items: list[ActivityOut]


# ── connections ───────────────────────────────────────────────────────────────
class ConnectionRequest(BaseModel):
    addressee_id: int
    message: str | None = Field(default=None, max_length=500)


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    addressee_id: int
    status: str
    message: str | None = None
    created_at: datetime
    updated_at: datetime
    other_user: PublicUserOut | None = None


# ── admin ─────────────────────────────────────────────────────────────────────
class ImportRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    fetched: int
    created: int
    updated: int
    unchanged: int
    duplicates: int
    rejected: int
    reject_reasons: dict
    error: str | None = None
    closed: int | None = None
    duration_ms: int | None = None


# ── admin user management ─────────────────────────────────────────────────────
class AdminUserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str | None = None
    email: str | None = None
    college: str | None = None
    degree: str | None = None
    graduation_year: int | None = None
    location: str | None = None
    skills: list[str] = []
    desired_roles: list[str] = []
    work_types: list[str] = []
    is_admin: bool = False
    is_active: bool = True
    is_onboarded: bool = False
    has_resume: bool = False
    resume_filename: str | None = None
    resume_size_bytes: int | None = None
    resume_uploaded_at: datetime | None = None
    missing_fields: list[str] = []
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None


class AdminUserDetail(AdminUserListItem):
    mobile: str | None = None
    gender: str | None = None
    branch: str | None = None
    cgpa: float | None = None
    bio: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    resume_content_type: str | None = None
    resume_skills: list[str] = []
    email_verified: bool = False
    saved_count: int = 0
    activity_count: int = 0
    connections_count: int = 0


class AdminUserPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AdminUserListItem]
