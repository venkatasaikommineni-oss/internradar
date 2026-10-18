"""Auth helpers: JWT creation/verification, password hashing, OTP generation."""
from __future__ import annotations

import hashlib
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt
from jwt import PyJWTError as JWTError

from .config import settings


# ── passwords ────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2:sha256:100000${salt}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hashed representation."""
    if not hashed or not plain:
        return False
    try:
        if hashed.startswith("pbkdf2:sha256:"):
            parts = hashed.split("$")
            if len(parts) >= 3:
                salt = parts[1]
                digest = parts[2]
                iters = 100_000
                if ":" in parts[0]:
                    try:
                        iters = int(parts[0].split(":")[-1])
                    except ValueError:
                        iters = 100_000
                dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), iters)
                return secrets.compare_digest(dk.hex(), digest)
        elif "$" in hashed:
            salt, digest = hashed.split("$", 1)
            dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 100_000)
            if secrets.compare_digest(dk.hex(), digest):
                return True
            return secrets.compare_digest(hashlib.sha256((salt + plain).encode("utf-8")).hexdigest(), digest)
        return secrets.compare_digest(hashlib.sha256(plain.encode("utf-8")).hexdigest(), hashed)
    except Exception:
        return False


# ── OTP ──────────────────────────────────────────────────────────────────────
def generate_otp(length: int = 6) -> str:
    """Cryptographically secure numeric OTP."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def hash_otp(otp: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + otp).encode("utf-8")).hexdigest()
    return f"{salt}${h}"


def verify_otp(otp: str, hashed: str) -> bool:
    if not hashed or not otp:
        return False
    try:
        if "$" in hashed:
            salt, h = hashed.split("$", 1)
            expected = hashlib.sha256((salt + otp).encode("utf-8")).hexdigest()
            return secrets.compare_digest(expected, h)
        return secrets.compare_digest(hashlib.sha256(otp.encode("utf-8")).hexdigest(), hashed)
    except Exception:
        return False


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(user_id: int, extra: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access", **(extra or {})}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, datetime]:
    """Returns (raw token, expiry). Store hash, send raw to client."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    raw = secrets.token_urlsafe(48)
    return raw, expire.replace(tzinfo=None)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None
    except Exception:
        return None


def hash_token(token: str) -> str:
    """SHA-256 hash for DB storage of refresh tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── verification token ────────────────────────────────────────────────────────
def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)
