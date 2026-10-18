"""Authentication endpoints: register, verify OTP, login, refresh, logout."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import RefreshToken, User, utcnow
from ..schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from ..services.email_validator import validate_email_deliverable

log = logging.getLogger("internradar.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Register account: validate email format + domain deliverability (without OTP),
    create user account, hash password, mark email_verified=True, and issue auth tokens."""
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Passwords do not match.",
        )

    is_valid, normalized_email, error_detail = validate_email_deliverable(body.email)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=error_detail or "Invalid or undeliverable email address.",
        )

    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing and existing.email_verified:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered. Please log in.")

    now = utcnow()
    if not existing:
        user = User(
            email=normalized_email,
            full_name=body.full_name,
            password_hash=hash_password(body.password),
            email_verified=True,
            is_active=True,
            last_login=now,
        )
        db.add(user)
    else:
        existing.full_name = body.full_name
        existing.password_hash = hash_password(body.password)
        existing.email_verified = True
        existing.last_login = now
        user = existing

    db.commit()
    db.refresh(user)

    access = create_access_token(user.id)
    raw_refresh, ref_exp = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=ref_exp,
    ))
    db.commit()

    return TokenResponse(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        is_onboarded=user.is_onboarded,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """Email + password login."""
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.password_hash:
        raise HTTPException(401, "Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    user.last_login = utcnow()
    db.commit()

    access = create_access_token(user.id)
    raw_refresh, ref_exp = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=ref_exp,
    ))
    db.commit()

    return TokenResponse(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        is_onboarded=user.is_onboarded,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for new access + refresh tokens."""
    h = hash_token(body.refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == h))
    if not stored or stored.revoked or stored.expires_at < utcnow():
        raise HTTPException(401, "Invalid or expired refresh token")

    # Rotate: revoke old, issue new
    stored.revoked = True
    user = db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or disabled")

    access = create_access_token(user.id)
    raw_refresh, ref_exp = create_refresh_token(user.id)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=ref_exp,
    ))
    db.commit()

    return TokenResponse(
        access_token=access,
        refresh_token=raw_refresh,
        user_id=user.id,
        is_onboarded=user.is_onboarded,
    )


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke the provided refresh token."""
    h = hash_token(body.refresh_token)
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == h))
    if stored:
        stored.revoked = True
        db.commit()
    return


@router.post("/change-password", status_code=200)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.password_hash or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(422, "New password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    # Revoke all refresh tokens to force re-login everywhere
    db.execute(
        RefreshToken.__table__.update().where(  # type: ignore[attr-defined]
            RefreshToken.user_id == user.id
        ).values(revoked=True)
    )
    db.commit()
    return {"detail": "Password changed. Please log in again."}
