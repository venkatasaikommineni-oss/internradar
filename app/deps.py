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


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if not settings.admin_api_key:
        raise HTTPException(403, "Admin API disabled: set ADMIN_API_KEY")
    if not secrets.compare_digest(x_admin_key or "", settings.admin_api_key):
        raise HTTPException(401, "Invalid admin key")
