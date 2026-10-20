"""Dependency injectors for FastAPI routes."""
from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .auth import decode_access_token
from .config import settings
from .database import get_db
from .models import User


def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """JWT Bearer auth or X-User-Id. Raises 401 when the credentials are missing or invalid."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id: int | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_access_token(token)
        if payload is not None:
            try:
                user_id = int(payload["sub"])
            except (KeyError, ValueError):
                pass
    elif x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError:
            pass

    if user_id is None:
        raise credentials_exception

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise credentials_exception
    return user


def get_current_verified_user(user: User = Depends(get_current_user)) -> User:
    """Like get_current_user but additionally requires email_verified."""
    if not user.email_verified:
        raise HTTPException(403, "Email address not verified")
    return user


class AdminPrincipal:
    """Represents authorized admin principal (either via user token or api key)."""
    def __init__(self, is_key: bool = False, user: User | None = None):
        self.is_key = is_key
        self.user = user

    @property
    def identifier(self) -> str:
        if self.user:
            return f"user:{self.user.id}:{self.user.email}"
        return "api_key"


def require_admin_access(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminPrincipal:
    """Authorize admin via X-Admin-Key OR via Bearer JWT / X-User-Id where user is an admin.
    Returns AdminPrincipal. Raises 401 if missing/invalid, 403 if user lacks admin privileges.
    """
    # 1. Check API Key header if provided
    if x_admin_key:
        if settings.admin_api_key and secrets.compare_digest(x_admin_key, settings.admin_api_key):
            return AdminPrincipal(is_key=True)
        raise HTTPException(status_code=401, detail="Invalid admin key")

    # 2. Check user credentials
    user_id: int | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = decode_access_token(token)
        if payload is not None:
            try:
                user_id = int(payload["sub"])
            except (KeyError, ValueError):
                pass
    elif x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError:
            pass

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for administrator access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Check is_admin or email in admin_emails
    admin_emails = [e.lower() for e in settings.admin_emails]
    user_email = (user.email or "").lower()
    is_admin = bool(user.is_admin) or (user_email in admin_emails)

    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return AdminPrincipal(is_key=False, user=user)


def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AdminPrincipal:
    """Backwards-compatible wrapper: accepts X-Admin-Key OR Bearer admin token."""
    return require_admin_access(
        authorization=authorization,
        x_admin_key=x_admin_key,
        x_user_id=x_user_id,
        db=db,
    )
