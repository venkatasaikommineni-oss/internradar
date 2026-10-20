"""Tests for Section 10: Mandatory profile details and private administrator user management."""
import io
import os
import uuid
import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User
from app.auth import create_access_token


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def regular_user():
    db = SessionLocal()
    email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        email=email,
        full_name="Student Test",
        password_hash="test_hash",
        email_verified=True,
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    token = create_access_token(user_id)
    yield {"id": user_id, "token": token, "email": email}
    # Teardown
    u = db.get(User, user_id)
    if u:
        if u.resume_path and os.path.exists(u.resume_path):
            try:
                os.remove(u.resume_path)
            except OSError:
                pass
        db.delete(u)
        db.commit()
    db.close()


@pytest.fixture
def admin_user():
    db = SessionLocal()
    email = f"admin_{uuid.uuid4().hex[:8]}@internradar.in"
    user = User(
        email=email,
        full_name="Platform Admin",
        password_hash="admin_hash",
        email_verified=True,
        is_active=True,
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    token = create_access_token(user_id)
    yield {"id": user_id, "token": token, "email": email}
    # Teardown
    u = db.get(User, user_id)
    if u:
        db.delete(u)
        db.commit()
    db.close()


def test_mandatory_profile_validation_rejects_empty_whitespace(client, regular_user):
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    # Whitespace full name
    res = client.put("/api/profile", json={"full_name": "   "}, headers=headers)
    assert res.status_code == 422
    assert "Full Name" in res.text or "cannot be empty" in res.text

    # Whitespace college
    res = client.put("/api/profile", json={"college": "   "}, headers=headers)
    assert res.status_code == 422

    # Invalid graduation year (out of 2020-2035 range)
    res = client.put("/api/profile", json={"graduation_year": 2018}, headers=headers)
    assert res.status_code == 422

    # Empty skills list
    res = client.put("/api/profile", json={"skills": []}, headers=headers)
    assert res.status_code == 422

    # Empty desired roles list
    res = client.put("/api/profile", json={"desired_roles": []}, headers=headers)
    assert res.status_code == 422

    # Empty work types list
    res = client.put("/api/profile", json={"work_types": []}, headers=headers)
    assert res.status_code == 422


def test_valid_profile_update_marks_onboarded(client, regular_user):
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    payload = {
        "full_name": "Aarav Sharma",
        "college": "IIT Bombay",
        "degree": "B.Tech",
        "graduation_year": 2026,
        "location": "Bengaluru",
        "skills": ["Python", "FastAPI"],
        "desired_roles": ["Backend Developer Intern"],
        "work_types": ["remote", "hybrid"],
        # Optional fields omitted or empty
        "linkedin_url": "",
        "github_url": "https://github.com/aarav",
        "portfolio_url": None,
        "mobile": "+91 9876543210",
        "bio": "Enthusiastic backend learner.",
    }

    res = client.put("/api/profile", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["full_name"] == "Aarav Sharma"
    assert data["college"] == "IIT Bombay"
    assert data["graduation_year"] == 2026
    assert data["is_onboarded"] is True
    assert data["linkedin_url"] is None
    assert data["github_url"] == "https://github.com/aarav"


def test_user_cannot_self_elevate_admin_status(client, regular_user):
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    # Attempt to send is_admin in profile update
    res = client.put("/api/profile", json={"is_admin": True, "full_name": "Hacker"}, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_admin"] is False


def test_resume_upload_validation_and_metadata(client, regular_user):
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    # 1. Invalid extension (.exe)
    res = client.post(
        "/api/profile/resume",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/x-msdownload")},
        headers=headers,
    )
    assert res.status_code == 415

    # 2. Spoofed PDF with fake magic bytes
    res = client.post(
        "/api/profile/resume",
        files={"file": ("fake.pdf", b"This is not a PDF file at all", "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 415
    assert "Missing %PDF-" in res.text

    # 3. Valid PDF with proper magic bytes
    valid_pdf = b"%PDF-1.4\n%test pdf binary content for internradar\n%%EOF"
    res = client.post(
        "/api/profile/resume",
        files={"file": ("my_resume_2026.pdf", valid_pdf, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["resume_filename"] == "my_resume_2026.pdf"
    assert data["resume_content_type"] == "application/pdf"
    assert data["resume_size_bytes"] == len(valid_pdf)
    assert data["resume_uploaded_at"] is not None

    # 4. User views/downloads own resume
    res = client.get("/api/profile/resume", headers=headers)
    assert res.status_code == 200
    assert res.content == valid_pdf
    assert "inline; filename=\"my_resume_2026.pdf\"" in res.headers["content-disposition"]

    # 5. User deletes own resume
    res = client.delete("/api/profile/resume", headers=headers)
    assert res.status_code == 200
    assert res.json()["resume_path"] is None
    assert res.json()["resume_filename"] is None

    # 6. Subsequent download returns 404
    res = client.get("/api/profile/resume", headers=headers)
    assert res.status_code == 404


def test_admin_authorization_enforcement(client, regular_user, admin_user):
    # Anonymous request -> 401
    res = client.get("/api/admin/users")
    assert res.status_code == 401

    # Regular user token -> 403 Forbidden
    reg_headers = {"Authorization": f"Bearer {regular_user['token']}"}
    res = client.get("/api/admin/users", headers=reg_headers)
    assert res.status_code == 403
    assert "Admin privileges required" in res.text

    # Admin user token -> 200 OK
    admin_headers = {"Authorization": f"Bearer {admin_user['token']}"}
    res = client.get("/api/admin/users", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data

    # X-Admin-Key header -> 200 OK (if set)
    res = client.get("/api/admin/users", headers={"X-Admin-Key": os.environ.get("ADMIN_API_KEY", "")})
    assert res.status_code in (200, 401)


def test_admin_inspect_user_and_download_resume(client, regular_user, admin_user):
    reg_headers = {"Authorization": f"Bearer {regular_user['token']}"}
    admin_headers = {"Authorization": f"Bearer {admin_user['token']}"}

    # Upload resume for regular user
    valid_pdf = b"%PDF-1.4\n%admin test resume file\n%%EOF"
    client.post(
        "/api/profile/resume",
        files={"file": ("student_cv.pdf", valid_pdf, "application/pdf")},
        headers=reg_headers,
    )

    # Admin inspects user detail
    res = client.get(f"/api/admin/users/{regular_user['id']}", headers=admin_headers)
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == regular_user["id"]
    assert detail["email"] == regular_user["email"]
    assert detail["has_resume"] is True
    assert detail["resume_filename"] == "student_cv.pdf"
    assert "missing_fields" in detail

    # Admin downloads regular user's resume
    res = client.get(f"/api/admin/users/{regular_user['id']}/resume", headers=admin_headers)
    assert res.status_code == 200
    assert res.content == valid_pdf

    # Regular user CANNOT access admin resume endpoint (IDOR prevention)
    res = client.get(f"/api/admin/users/{regular_user['id']}/resume", headers=reg_headers)
    assert res.status_code == 403
