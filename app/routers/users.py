"""User profile, resume upload, public profiles, connections."""
from __future__ import annotations

import io
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_current_verified_user
from ..models import User, UserConnection, utcnow
from ..schemas import (
    ConnectionOut,
    ConnectionRequest,
    ProfileUpdate,
    PublicUserOut,
    UserOut,
)
from ..services.geo import canonical_city_exact, suggest_cities
from ..services.resume_parser import extract_skills_from_text, extract_text
from ..services.skills import canonical_role, canonical_skill

log = logging.getLogger("internradar.users")
router = APIRouter(prefix="/api", tags=["profile"])

_ALLOWED_RESUME_EXTS = {".pdf", ".docx", ".txt"}
_ALLOWED_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_resume_file(content: bytes, ext: str) -> str:
    """Validate magic bytes / signatures and return normalized MIME content type.
    Rejects disguised executables or corrupt files.
    """
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(415, "Invalid PDF file: Missing %PDF- signature.")
        return "application/pdf"
    elif ext == ".docx":
        if not content.startswith(b"PK\x03\x04"):
            raise HTTPException(415, "Invalid DOCX file: Missing PK archive signature.")
        try:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = zf.namelist()
                if not any(n.startswith("word/") or n == "[Content_Types].xml" for n in names):
                    raise HTTPException(415, "Invalid DOCX file: Missing Word document structure.")
        except zipfile.BadZipFile:
            raise HTTPException(415, "Invalid DOCX file: Corrupt ZIP archive.")
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif ext == ".txt":
        if b"\x00" in content:
            raise HTTPException(415, "Invalid TXT file: Contains binary null bytes.")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                content.decode("latin-1")
            except Exception:
                raise HTTPException(415, "Invalid TXT file: Unable to decode text content.")
        return "text/plain"
    else:
        raise HTTPException(415, f"Unsupported file extension: {ext}")


def get_safe_resume_path(file_path: str | None) -> str:
    """Ensure path traversal protection and verify resume file exists in private upload dir."""
    if not file_path:
        raise HTTPException(404, "No resume uploaded.")
    real_base = os.path.realpath(settings.upload_dir)
    real_target = os.path.realpath(file_path)
    if not (real_target.startswith(real_base + os.sep) or real_target == real_base):
        log.warning("Path traversal attempt blocked: base=%s target=%s", real_base, real_target)
        raise HTTPException(400, "Invalid resume file path.")
    if not os.path.isfile(real_target):
        raise HTTPException(404, "Resume file not found on disk.")
    return real_target


@router.post("/users", status_code=201)
def create_user_direct(
    payload: dict = {},
    db: Session = Depends(get_db),
):
    """Direct user creation for testing and swift onboarding."""
    import secrets
    full_name = payload.get("full_name") or "Student"
    email = payload.get("email") or f"user_{secrets.token_hex(4)}@example.com"
    user = User(
        email=email,
        full_name=full_name,
        email_verified=True,
        is_active=True,
        skills=[],
        desired_roles=[],
        work_types=[],
        specializations=[],
    )
    for k, v in payload.items():
        if hasattr(user, k) and k not in ("id", "created_at", "updated_at", "is_admin"):
            setattr(user, k, v)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


# ── own profile ───────────────────────────────────────────────────────────────
@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)):
    return user


@router.put("/profile", response_model=UserOut)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update own profile. Curated fields (location/skills/roles) validated against allowed lists."""
    data = body.model_dump(exclude_unset=True)
    errors: dict[str, str] = {}

    if "location" in data and data["location"] is not None:
        city = canonical_city_exact(data["location"])
        if city is None:
            errors["location"] = "Unknown location; choose one from /api/meta/locations"
        data["location"] = city

    if data.get("skills") is not None:
        canon = [canonical_skill(s) for s in data["skills"]]
        bad = [s for s, c in zip(data["skills"], canon) if c is None]
        if bad:
            errors["skills"] = f"Unknown skills: {bad}"
        data["skills"] = sorted({c for c in canon if c})

    if data.get("specializations") is not None:
        # Specializations are free-form but limited in length
        data["specializations"] = [s[:80] for s in data["specializations"][:10]]

    if data.get("desired_roles") is not None:
        canon = [canonical_role(r) for r in data["desired_roles"]]
        bad = [r for r, c in zip(data["desired_roles"], canon) if c is None]
        if bad:
            errors["desired_roles"] = f"Unknown roles: {bad}"
        data["desired_roles"] = list(dict.fromkeys(c for c in canon if c))

    if data.get("work_types") is not None:
        data["work_types"] = sorted(set(data["work_types"]))

    if errors:
        raise HTTPException(422, errors)

    # Protect immutable / sensitive fields
    data.pop("is_admin", None)
    data.pop("id", None)
    data.pop("email", None)

    for k, v in data.items():
        setattr(user, k, v)
    user.updated_at = utcnow()

    # Mark onboarded if key mandatory fields are filled
    is_complete = bool(
        user.full_name
        and user.college
        and user.degree
        and user.graduation_year
        and user.location
        and (user.skills and len(user.skills) > 0)
        and (user.desired_roles and len(user.desired_roles) > 0)
        and (user.work_types and len(user.work_types) > 0)
    )
    user.is_onboarded = is_complete

    db.commit()
    return user


# ── resume upload & management ────────────────────────────────────────────────
@router.post("/profile/resume", response_model=UserOut)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a PDF/DOCX/TXT resume. Validates magic bytes, enforces size limit,
    tracks metadata, and auto-extracts skills into profile."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_RESUME_EXTS:
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(_ALLOWED_RESUME_EXTS)}")

    content = await file.read()
    if len(content) > settings.max_resume_size_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large. Maximum size: {settings.max_resume_size_mb} MB")

    # Validate magic bytes / file structure
    content_type = validate_resume_file(content, ext)

    # Ensure upload directory
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Clean previous resume file if it exists
    if user.resume_path:
        try:
            old_path = get_safe_resume_path(user.resume_path)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass

    original_filename = os.path.basename(file.filename or "resume")[:250]
    safe_storage_name = f"resume_{user.id}_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(settings.upload_dir, safe_storage_name)

    with open(save_path, "wb") as f:
        f.write(content)

    # Extract text and skills
    text = extract_text(content, file.filename or "")
    skills = extract_skills_from_text(text)

    user.resume_path = save_path
    user.resume_filename = original_filename
    user.resume_content_type = content_type
    user.resume_size_bytes = len(content)
    user.resume_uploaded_at = utcnow()
    user.resume_text = text[:50000]  # cap stored text
    user.resume_skills = skills

    # Merge resume skills into profile skills (deduplicated)
    merged = sorted(set((user.skills or []) + skills))
    user.skills = merged
    user.updated_at = utcnow()
    db.commit()

    log.info("User %s uploaded resume '%s' (%d bytes); extracted %d skills", user.id, original_filename, len(content), len(skills))
    return user


@router.get("/profile/resume")
def download_my_resume(
    download: bool = Query(False, description="Whether to trigger file download"),
    user: User = Depends(get_current_user),
):
    """Download or preview own resume with authorization and path verification."""
    safe_path = get_safe_resume_path(user.resume_path)
    filename = user.resume_filename or os.path.basename(safe_path)
    disposition = "attachment" if download else "inline"
    return FileResponse(
        safe_path,
        media_type=user.resume_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


@router.delete("/profile/resume", response_model=UserOut)
def delete_my_resume(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete own resume file and metadata."""
    if user.resume_path:
        try:
            safe_path = get_safe_resume_path(user.resume_path)
            if os.path.exists(safe_path):
                os.remove(safe_path)
        except Exception as e:
            log.warning("Could not delete resume file for user %s: %s", user.id, e)

    user.resume_path = None
    user.resume_filename = None
    user.resume_content_type = None
    user.resume_size_bytes = None
    user.resume_uploaded_at = None
    user.resume_text = None
    user.resume_skills = []
    user.updated_at = utcnow()
    db.commit()
    return user


# ── profile photo ─────────────────────────────────────────────────────────────
@router.post("/profile/photo", response_model=UserOut)
async def upload_photo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_PHOTO_EXTS:
        raise HTTPException(415, f"Unsupported image type. Allowed: {', '.join(_ALLOWED_PHOTO_EXTS)}")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Photo must be under 2 MB")

    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = f"photo_{user.id}_{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(settings.upload_dir, filename)
    with open(save_path, "wb") as f:
        f.write(content)

    if user.profile_photo and os.path.exists(user.profile_photo):
        try:
            os.remove(user.profile_photo)
        except OSError:
            pass

    user.profile_photo = save_path
    user.updated_at = utcnow()
    db.commit()
    return user


# ── public profiles ───────────────────────────────────────────────────────────
@router.get("/users/{user_id}", response_model=PublicUserOut)
def get_public_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get another user's public profile. Only accessible to authenticated users."""
    target = db.get(User, user_id)
    if not target or not target.is_active:
        raise HTTPException(404, "User not found")
    if target.id == current_user.id:
        raise HTTPException(400, "Use /api/profile to view your own profile")
    return target


@router.get("/users", response_model=list[PublicUserOut])
def search_users(
    q: str | None = Query(None, description="Search by name or college"),
    skills: str | None = Query(None, description="comma-separated skills to filter"),
    location: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Discover other students on InternRadar."""
    conds = [User.is_active == True, User.id != current_user.id, User.is_onboarded == True]  # noqa: E712
    if q:
        conds.append(
            User.full_name.icontains(q, autoescape=True) | User.college.icontains(q, autoescape=True)
        )
    if location:
        conds.append(User.location.icontains(location, autoescape=True))
    rows = db.scalars(select(User).where(*conds).limit(limit).offset(offset)).all()
    if skills:
        wanted = {s.strip().lower() for s in skills.split(",") if s.strip()}
        rows = [r for r in rows if wanted & {s.lower() for s in (r.skills or [])}]
    return rows


# ── connections ───────────────────────────────────────────────────────────────
@router.post("/connections", response_model=ConnectionOut, status_code=201)
def send_connection_request(
    body: ConnectionRequest,
    user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db),
):
    if body.addressee_id == user.id:
        raise HTTPException(400, "Cannot connect with yourself")
    addressee = db.get(User, body.addressee_id)
    if not addressee or not addressee.is_active:
        raise HTTPException(404, "User not found")

    existing = db.scalar(
        select(UserConnection).where(
            or_(
                and_(UserConnection.requester_id == user.id, UserConnection.addressee_id == body.addressee_id),
                and_(UserConnection.requester_id == body.addressee_id, UserConnection.addressee_id == user.id),
            )
        )
    )
    if existing:
        if existing.status == "accepted":
            raise HTTPException(409, "Already connected")
        if existing.status == "pending":
            raise HTTPException(409, "Connection request already pending")
        if existing.status == "blocked":
            raise HTTPException(403, "Cannot send connection request")
        # Rejected: allow re-request
        existing.status = "pending"
        existing.message = body.message
        existing.updated_at = utcnow()
        existing.requester_id = user.id
        existing.addressee_id = body.addressee_id
        db.commit()
        conn = existing
    else:
        conn = UserConnection(
            requester_id=user.id,
            addressee_id=body.addressee_id,
            message=body.message,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)

    # Attach public profile
    result = ConnectionOut.model_validate(conn)
    result.other_user = PublicUserOut.model_validate(addressee)
    return result


@router.get("/connections", response_model=list[ConnectionOut])
def list_connections(
    status: str | None = Query(None, description="pending|accepted|rejected"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List connections where the current user is requester or addressee."""
    conds = [
        or_(
            UserConnection.requester_id == user.id,
            UserConnection.addressee_id == user.id,
        )
    ]
    if status:
        conds.append(UserConnection.status == status)

    rows = db.scalars(select(UserConnection).where(*conds).order_by(UserConnection.created_at.desc())).all()
    out = []
    for conn in rows:
        other_id = conn.addressee_id if conn.requester_id == user.id else conn.requester_id
        other = db.get(User, other_id)
        item = ConnectionOut.model_validate(conn)
        if other:
            item.other_user = PublicUserOut.model_validate(other)
        out.append(item)
    return out


@router.put("/connections/{connection_id}", response_model=ConnectionOut)
def respond_to_connection(
    connection_id: int,
    action: str = Query(..., description="accept|reject|block"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = db.get(UserConnection, connection_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    if conn.addressee_id != user.id and action != "block":
        raise HTTPException(403, "Not authorized to respond to this request")

    if action not in ("accept", "reject", "block"):
        raise HTTPException(400, "action must be accept, reject, or block")

    status_map = {"accept": "accepted", "reject": "rejected", "block": "blocked"}
    conn.status = status_map[action]
    conn.updated_at = utcnow()
    db.commit()
    return conn


@router.delete("/connections/{connection_id}", status_code=204)
def remove_connection(
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = db.get(UserConnection, connection_id)
    if not conn:
        raise HTTPException(404, "Connection not found")
    if conn.requester_id != user.id and conn.addressee_id != user.id:
        raise HTTPException(403, "Not authorized")
    db.delete(conn)
    db.commit()
