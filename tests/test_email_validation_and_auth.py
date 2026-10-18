"""Tests for email format, domain deliverability validation, and OTP-free signup."""
import os
import tempfile
import unittest.mock
from unittest.mock import patch

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_auth.db"
os.environ["ENABLE_SCHEDULER"] = "false"

import dns.resolver
import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User
from app.services.email_validator import validate_email_deliverable
from app.auth import verify_password


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def test_validate_email_syntax_error():
    """Test 3: malformed email address rejection."""
    # Missing @ sign
    valid, normalized, err = validate_email_deliverable("notanemail")
    assert not valid
    assert "Invalid email format" in err or "must have an @-sign" in err

    # Empty email
    valid, _, err = validate_email_deliverable("")
    assert not valid

    # Malformed domain / double dot
    valid, _, err = validate_email_deliverable("test@..com")
    assert not valid


def test_validate_email_nonexistent_domain():
    """Test 4: address with nonexistent domain rejection."""
    valid, normalized, err = validate_email_deliverable("student@nonexistentdomainthatdoesnotexist999888.com")
    assert not valid
    assert "does not exist" in err.lower() or "undeliverable" in err.lower()


def test_validate_email_valid_deliverable_domain():
    """Test 5: syntactically valid email at a domain with working mail records."""
    valid, normalized, err = validate_email_deliverable("STUDENT@GMAIL.COM")
    assert valid
    assert normalized == "student@gmail.com"  # normalized lowercase
    assert err == ""


def test_validate_email_dns_timeout_graceful_fallback():
    """Test 7: DNS timeouts and temporary network failures handled gracefully."""
    # When dns.resolver.resolve raises Timeout or LifetimeTimeout,
    # the validator falls back to syntax validation rather than rejecting valid addresses.
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.LifetimeTimeout):
        valid, normalized, err = validate_email_deliverable("test@gmail.com")
        assert valid
        assert normalized == "test@gmail.com"

    # With transient error message
    with patch("email_validator.deliverability.validate_email_deliverability", side_effect=dns.exception.Timeout("DNS query timed out")):
        valid, normalized, err = validate_email_deliverable("developer@microsoft.com")
        assert valid
        assert normalized == "developer@microsoft.com"


def test_disposable_domain_rejected():
    """Disposable domains are rejected."""
    valid, _, err = validate_email_deliverable("user@mailinator.com")
    assert not valid
    assert "Disposable" in err


def test_signup_with_malformed_email(client):
    """Signup endpoint rejects malformed emails with 422."""
    res = client.post("/api/auth/register", json={
        "email": "not-an-email",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Test User",
    })
    assert res.status_code == 422


def test_signup_with_nonexistent_domain(client):
    """Signup endpoint rejects emails with undeliverable domains with 422."""
    res = client.post("/api/auth/register", json={
        "email": "user@nonexistentdomain99998888.org",
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "Test User",
    })
    assert res.status_code == 422
    assert "does not exist" in res.json()["detail"].lower() or "undeliverable" in res.json()["detail"].lower()


def test_signup_password_mismatch(client):
    """Signup rejects mismatched confirm_password."""
    res = client.post("/api/auth/register", json={
        "email": "user@gmail.com",
        "password": "Password123!",
        "confirm_password": "DifferentPassword123!",
        "full_name": "Test User",
    })
    assert res.status_code == 422


def test_valid_signup_flow_no_otp(client):
    """Test 6: Valid signup proceeds directly without OTP, returns JWT tokens."""
    email = "newstudent@gmail.com"
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "full_name": "Radha Sharma",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Confirm user is in database and email_verified is True
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.email_verified is True
    assert user.full_name == "Radha Sharma"
    assert verify_password("SecurePassword123!", user.password_hash)
    db.close()


def test_duplicate_signup_rejected(client):
    """Test 6b: Duplicate signup returns 409 Conflict."""
    email = "newstudent@gmail.com"
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "full_name": "Radha Sharma",
    })
    assert res.status_code == 409
    assert "already registered" in res.json()["detail"].lower()


def test_login_works_for_created_user(client):
    """Test 9: User created via signup can log in successfully."""
    res = client.post("/api/auth/login", json={
        "email": "newstudent@gmail.com",
        "password": "SecurePassword123!",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
