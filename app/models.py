from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow() -> datetime:
    """Naive UTC timestamp (all datetimes in the DB are UTC, tz-naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Internship(Base):
    __tablename__ = "internships"
    __table_args__ = (
        UniqueConstraint("source_name", "external_id", name="uq_source_external"),
        Index("ix_internships_status_deadline", "status", "deadline"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # identity / dedup
    fingerprint: Mapped[str] = mapped_column(String(40), index=True)
    apply_url_key: Mapped[str] = mapped_column(String(1000), index=True)
    source_name: Mapped[str] = mapped_column(String(60))
    external_id: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(1000))

    # content
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), index=True)
    company_website: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list] = mapped_column(JSON, default=list)
    skills_blob: Mapped[str] = mapped_column(Text, default="")
    eligibility: Mapped[str | None] = mapped_column(Text)
    grad_years: Mapped[list] = mapped_column(JSON, default=list)

    location: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    work_type: Mapped[str | None] = mapped_column(String(10), index=True)

    stipend_text: Mapped[str | None] = mapped_column(String(200))
    stipend_min: Mapped[int | None] = mapped_column(Integer)
    stipend_max: Mapped[int | None] = mapped_column(Integer)
    duration_text: Mapped[str | None] = mapped_column(String(100))
    duration_months: Mapped[float | None] = mapped_column(Float)

    deadline: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    application_url: Mapped[str] = mapped_column(String(1000))

    # maintenance
    status: Mapped[str] = mapped_column(String(15), default="unverified", index=True)
    status_basis: Mapped[str] = mapped_column(String(15), default="none")
    link_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    validation_status: Mapped[str] = mapped_column(String(10), default="partial")

    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # view / apply tracking counts (aggregate — per-user tracking is in UserActivity)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    apply_click_count: Mapped[int] = mapped_column(Integer, default=0)


class User(Base):
    """Student account with full profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))  # bcrypt hash

    # profile
    gender: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(100))
    college: Mapped[str | None] = mapped_column(String(200))
    mobile: Mapped[str | None] = mapped_column(String(20))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    bio: Mapped[str | None] = mapped_column(Text)
    profile_photo: Mapped[str | None] = mapped_column(String(500))  # stored path

    skills: Mapped[list] = mapped_column(JSON, default=list)
    specializations: Mapped[list] = mapped_column(JSON, default=list)
    desired_roles: Mapped[list] = mapped_column(JSON, default=list)
    work_types: Mapped[list] = mapped_column(JSON, default=list)
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    degree: Mapped[str | None] = mapped_column(String(100))
    branch: Mapped[str | None] = mapped_column(String(100))
    cgpa: Mapped[float | None] = mapped_column(Float)

    # resume
    resume_path: Mapped[str | None] = mapped_column(String(500))
    resume_text: Mapped[str | None] = mapped_column(Text)   # extracted plain text for AI
    resume_skills: Mapped[list] = mapped_column(JSON, default=list)  # skills parsed from resume

    # auth state
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, default=False)

    # notification preferences
    notify_new_matches: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_deadline: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)


class EmailVerification(Base):
    """OTP challenges for email verification during registration."""

    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    otp_hash: Mapped[str] = mapped_column(String(200))         # bcrypt hash of the 6-digit code
    token: Mapped[str] = mapped_column(String(100), unique=True, index=True)  # bearer token after OTP pass
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RefreshToken(Base):
    """Long-lived refresh tokens (JWT)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    device_info: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SavedInternship(Base):
    __tablename__ = "saved_internships"
    __table_args__ = (UniqueConstraint("user_id", "internship_id", name="uq_user_internship"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internships.id", ondelete="CASCADE"))
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text)  # personal notes on saved internship


class UserActivity(Base):
    """Per-user activity: viewed, applied, bookmarked events."""

    __tablename__ = "user_activities"
    __table_args__ = (
        Index("ix_activity_user_intern", "user_id", "internship_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    internship_id: Mapped[int] = mapped_column(ForeignKey("internships.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20), index=True)
    # action values: "viewed" | "apply_clicked" | "bookmarked" | "unbookmarked" | "noted"
    detail: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class UserConnection(Base):
    """Student-to-student connection requests."""

    __tablename__ = "user_connections"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_connection_pair"),
        Index("ix_connections_addressee", "addressee_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    addressee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(15), default="pending", index=True)
    # status: pending | accepted | rejected | blocked
    message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(10), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    unchanged: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    reject_reasons: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))
    closed: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
