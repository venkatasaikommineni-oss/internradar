from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.ai.engine import StudentProfile, Internship, normalize_listing, recommend
from app.ai.normalize import Reject
from app.ai.status import compute_status
from app.ai.skills import extract_skills

def test_skill_extraction_aliases():
    got = extract_skills("Built ReactJS frontend with Python and RESTful APIs")
    assert "React" in got and "Python" in got and "REST APIs" in got

def test_normalize_valid_internship():
    row = normalize_listing({"title":"Python Developer Intern", "company":"Acme", "description":"Python SQL", "application_url":"https://example.com/apply", "location":"Remote India"}, "test")
    assert row["title"] == "Python Developer Intern"
    assert "Python" in row["skills"]
    assert row["work_type"] == "remote"

def test_normalize_rejects_non_internship():
    with pytest.raises(Reject):
        normalize_listing({"title":"Software Engineer", "company":"Acme", "application_url":"https://example.com/apply"}, "test")

def test_recommendation_explains_skill_match():
    profile = StudentProfile(skills=["Python", "SQL"], desired_roles=["Data Science Intern"], work_types=["remote"], location="Guntur", graduation_year=2028)
    listing = Internship(title="Data Science Intern", company="Acme", description="Python and SQL", skills=["Python", "SQL", "Pandas"], grad_years=[2028], location="Remote", city=None, work_type="remote")
    result = recommend(profile, listing)
    assert 0 <= result["score"] <= 100
    assert result["matched_skills"] == ["Python", "SQL"]
    assert result["missing_skills"] == ["Pandas"]
    assert result["eligibility"]["status"] == "eligible"
    assert result["reasons"]

def test_missing_deadline_is_unverified():
    assert compute_status(None)[0] == "unverified"

def test_expired_deadline():
    now = datetime.now(timezone.utc)
    assert compute_status(now - timedelta(days=1), now=now)[0] == "expired"
