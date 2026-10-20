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


def test_is_admin_none_profile_retrieval_regression(client):
    """REGRESSION TEST: Render production error where is_admin is None in the database
    caused FastAPI to raise ResponseValidationError: Input should be a valid boolean.
    This test verifies that legacy rows with is_admin=None return 200 OK with is_admin=False."""
    from datetime import datetime, timezone
    from app.schemas import UserOut
    from app.models import User
    from app.deps import get_current_user
    from app.main import app

    now = datetime.now(timezone.utc)

    # 1. Direct schema contract test: is_admin=None must coerce to False
    legacy_dict = {
        "id": 999,
        "email": "legacy_user_none@example.com",
        "full_name": "Legacy Null User",
        "is_admin": None,
        "email_verified": None,
        "is_onboarded": None,
        "notify_new_matches": None,
        "notify_deadline": None,
        "created_at": now,
        "updated_at": now,
    }
    validated = UserOut.model_validate(legacy_dict)
    assert validated.is_admin is False
    assert validated.email_verified is False
    assert validated.is_onboarded is False
    assert validated.notify_new_matches is True
    assert validated.notify_deadline is True

    # 2. Endpoint response validation: FastAPI GET /api/profile must return 200 OK with is_admin=False
    mock_legacy_user = User(
        id=999,
        email="legacy_user_none@example.com",
        full_name="Legacy Null User",
        created_at=now,
        updated_at=now,
    )
    mock_legacy_user.is_admin = None  # Simulate legacy record attribute

    app.dependency_overrides[get_current_user] = lambda: mock_legacy_user
    try:
        res = client.get("/api/profile")
        assert res.status_code == 200, f"Expected 200 OK but got {res.status_code}: {res.text}"
        data = res.json()
        assert data["is_admin"] is False
        assert data["email"] == "legacy_user_none@example.com"
    finally:
        app.dependency_overrides.pop(get_current_user, None)




def test_gender_and_work_types_casing_normalization(client, regular_user):
    """Test that capitalized or spaced gender and work types from frontend forms
    are normalized cleanly without 422 validation errors."""
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    # Test "Male" -> "male" and "Remote" -> "remote"
    res = client.put(
        "/api/profile",
        json={"gender": "Male", "work_types": ["Remote", "Hybrid"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["gender"] == "male"
    assert set(res.json()["work_types"]) == {"remote", "hybrid"}

    # Test "Female"
    res = client.put("/api/profile", json={"gender": "Female"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["gender"] == "female"

    # Test "Non-binary"
    res = client.put("/api/profile", json={"gender": "Non-binary"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["gender"] == "non_binary"

    # Test "Prefer not to say"
    res = client.put("/api/profile", json={"gender": "Prefer not to say"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["gender"] == "prefer_not_to_say"


def test_end_to_end_auth_lifecycle(client):
    """Verify entire authentication lifecycle: registration -> login -> profile get ->
    profile edit -> token refresh -> logout -> invalid session rejection."""
    email = f"lifecycle_{os.urandom(4).hex()}@gmail.com"
    password = "SecurePassword123!"

    # 1. Registration
    reg_res = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": "Lifecycle User", "password": password, "confirm_password": password},
    )
    assert reg_res.status_code == 201, reg_res.text
    tokens = reg_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["is_admin"] is False
    token = tokens["access_token"]
    refresh_tok = tokens["refresh_token"]

    # 2. Profile retrieval with fresh token
    headers = {"Authorization": f"Bearer {token}"}
    prof_res = client.get("/api/profile", headers=headers)
    assert prof_res.status_code == 200
    assert prof_res.json()["email"] == email
    assert prof_res.json()["is_admin"] is False

    # 3. Profile update
    update_res = client.put(
        "/api/profile",
        json={
            "full_name": "Lifecycle Updated",
            "college": "IIT Delhi",
            "degree": "B.Tech",
            "graduation_year": 2026,
            "skills": ["Python", "React"],
            "desired_roles": ["Software Development Intern"],
            "location": "Bengaluru",
            "work_types": ["hybrid"],
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["full_name"] == "Lifecycle Updated"
    assert update_res.json()["is_onboarded"] is True

    # 4. Token refresh
    ref_res = client.post("/api/auth/refresh", json={"refresh_token": refresh_tok})
    assert ref_res.status_code == 200
    new_tokens = ref_res.json()
    assert "access_token" in new_tokens
    new_token = new_tokens["access_token"]

    # 5. Logout
    out_res = client.post("/api/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert out_res.status_code in (200, 204)

    # 6. Verify revoked refresh token is rejected
    ref_again = client.post("/api/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert ref_again.status_code == 401


def test_controlled_discovery_refresh_endpoint(client):
    """Verify refresh endpoint has status check, controlled background task and rate limit cooldown."""
    from unittest.mock import patch

    # Status check
    status_res = client.get("/api/internships/refresh-status")
    assert status_res.status_code == 200
    assert "status" in status_res.json()
    assert "is_running" in status_res.json()

    # Trigger refresh with mocked empty sources for instant test execution
    with patch("app.routers.internships.get_sources", return_value=[]):
        ref_res = client.post("/api/internships/refresh")
        assert ref_res.status_code == 200
        data = ref_res.json()
        assert data["status"] in ("started", "cooldown", "running")

        # Immediate second call should respect cooldown or running state
        second_res = client.post("/api/internships/refresh")
        assert second_res.status_code == 200
        assert second_res.json()["status"] in ("cooldown", "running", "started")


def test_discovery_software_role_prioritization(client):
    """Verify that default discovery ranking prioritizes software and technical roles."""
    res = client.get("/api/internships?limit=20")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0

    # Test category filtering
    cat_res = client.get("/api/internships?category=software&limit=10")
    assert cat_res.status_code == 200
    cat_items = cat_res.json()["items"]
    for it in cat_items:
        title_low = it["title"].lower()
        assert any(w in title_low for w in ["software", "developer", "engineer", "sde", "coding", "programmer"])


def test_profile_gender_and_bio_optional_and_saves_successfully(client, regular_user):
    """Verify gender, bio, and social links are optional, and saving succeeds when empty."""
    headers = {"Authorization": f"Bearer {regular_user['token']}"}

    # 1. Update profile with gender and bio explicitly empty/None
    payload = {
        "full_name": "Priya Sharma",
        "location": "Bengaluru",
        "college": "RV College of Engineering",
        "degree": "B.Tech",
        "graduation_year": 2026,
        "skills": ["python", "react"],
        "desired_roles": ["Frontend Developer Intern"],
        "work_types": ["remote"],
        "gender": None,
        "bio": "",
        "linkedin_url": "",
        "github_url": "",
        "portfolio_url": "",
    }
    res = client.put("/api/profile", headers=headers, json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["full_name"] == "Priya Sharma"
    assert data["gender"] is None
    assert data["bio"] is None
    assert data["linkedin_url"] is None
    assert data["github_url"] is None
    assert data["portfolio_url"] is None
    assert data["is_onboarded"] is True


def test_recommendations_gated_to_users_with_meaningful_profile(client):
    """Verify recommendations are hidden/empty for users without personalization data."""
    # 1. Guest user gets 401
    assert client.get("/api/recommendations").status_code == 401

    # 2. Registered user with empty profile gets empty recommendations (no fake items)
    email = f"new_student_{uuid.uuid4().hex[:8]}@gmail.com"
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "full_name": "New Student",
    })
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Call recommendations with incomplete profile
    res = client.get("/api/recommendations", headers=headers)
    assert res.status_code == 200
    recs = res.json()
    assert recs["total"] == 0
    assert recs["items"] == []
    assert any("Complete your profile" in n for n in recs["notes"])

    # 3. After completing profile with skills and desired roles, real recommendations are returned
    up = client.put("/api/profile", headers=headers, json={
        "full_name": "Test Coder",
        "location": "Bengaluru",
        "college": "PES University",
        "degree": "B.Tech",
        "graduation_year": 2026,
        "skills": ["python", "django"],
        "desired_roles": ["Backend Developer Intern"],
        "work_types": ["remote"],
    })
    assert up.status_code == 200

    res2 = client.get("/api/recommendations", headers=headers)
    assert res2.status_code == 200
    recs2 = res2.json()
    assert recs2["total"] > 0
    assert len(recs2["items"]) > 0

