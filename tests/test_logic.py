"""Framework-free tests of the core logic (normalisation, skills, scoring)."""
from datetime import datetime
from types import SimpleNamespace as NS

import pytest

from app.services.geo import canonical_city_exact, normalize_city
from app.services.normalize import (
    Reject, canonical_url, extract_grad_years, normalize_record, parse_deadline,
    parse_duration, parse_stipend,
)
from app.services.scoring import score_internship
from app.services.skills import canonical_skill, extract_skills

W = {"skills": 0.55, "interest": 0.20, "location": 0.15, "work_type": 0.10}


def raw(**kw):
    base = dict(title="Python Developer Intern", company="Acme", application_url="https://acme.com/jobs/1?utm_source=x",
                description="Work with Python, SQL and Django. Batch 2026/2027 only.", location="Bangalore, India")
    base.update(kw)
    return base


def test_skill_extraction_boundaries():
    s = extract_skills("Need JavaScript, React Native, C++ and C#. node.js ok; golang too")
    assert {"JavaScript", "React Native", "C++", "C#", "Node.js", "Go"} <= set(s)
    assert "React" not in s and "Java" not in s
    assert canonical_skill("PyTorch") == "PyTorch" and canonical_skill("sklearn") == "Scikit-learn"
    assert canonical_skill("underwater basket weaving") is None


def test_city_normalisation():
    assert normalize_city("Bangalore, India") == "Bengaluru"
    assert normalize_city("Remote") is None
    assert canonical_city_exact("gurgaon") == "Gurugram"
    assert canonical_city_exact("Atlantis") is None


def test_stipend_duration_deadline():
    assert parse_stipend("₹10,000 - 15,000 /month") == (10000, 15000)
    assert parse_stipend("Unpaid") == (0, 0)
    assert parse_stipend("$500") == (None, None)
    assert parse_stipend("3.6 LPA") == (30000, 30000)
    assert parse_stipend(None) == (None, None)
    assert parse_duration("3 months") == 3.0 and parse_duration("12 weeks") == 2.8
    d = parse_deadline("2026-10-30")
    assert d == datetime(2026, 10, 30, 18, 29, 59)  # 23:59:59 IST in UTC
    assert parse_deadline("not a date") is None


def test_url_validation():
    assert canonical_url("https://A.com/x/?utm_source=t&id=2#frag") == "https://a.com/x?id=2"
    for bad in ("ftp://a.com", "http://localhost/x", "http://10.0.0.1/x", "javascript:alert(1)", "", None, "https://intranet/x"):
        assert canonical_url(bad) is None


def test_grad_years():
    assert extract_grad_years("Open to 2026 and 2027 graduates") == []  # year before keyword is not matched
    assert extract_grad_years("Graduating batch: 2026, 2027") == [2026, 2027]
    assert extract_grad_years("Batch 2025-2027") == [2025, 2026, 2027]


def test_normalize_record_and_rejects():
    rec = normalize_record(raw(), "src")
    assert rec["city"] == "Bengaluru" and rec["work_type"] == "onsite"
    assert {"Python", "SQL", "Django"} <= set(rec["skills"]) and rec["skills_blob"].startswith("|")
    assert rec["grad_years"] == [2026, 2027]
    assert rec["apply_url_key"] == "https://acme.com/jobs/1"
    assert rec["deadline"] is None  # never invented
    with pytest.raises(Reject, match="not_internship"):
        normalize_record(raw(title="Senior Engineer"), "src")
    with pytest.raises(Reject, match="invalid_application_url"):
        normalize_record(raw(application_url="not a url"), "src")
    with pytest.raises(Reject, match="missing_company"):
        normalize_record(raw(company=" "), "src")
    # same opportunity, different wording/tracking -> same fingerprint & url key
    a = normalize_record(raw(title="Python Developer Internship"), "s2")
    assert a["fingerprint"] == rec["fingerprint"]


def mk(**kw):
    base = dict(title="Python Developer Intern", skills=["Python", "SQL"], description="", work_type="onsite",
                city="Hyderabad", eligibility=None, grad_years=[])
    base.update(kw)
    return NS(**base)


def user(**kw):
    base = dict(skills=["Python"], desired_roles=["Software Development Intern"], location="Hyderabad",
                work_types=["onsite"], graduation_year=2027)
    base.update(kw)
    return NS(**base)


def test_scoring_weights_and_missing_data():
    r = score_internship(user(), mk(), W)
    assert r["matched_skills"] == ["Python"] and r["missing_skills"] == ["SQL"]
    # Python is named in the title so it counts double: 2 / (2 + 1)
    assert r["breakdown"]["skills"] == 0.67 and r["breakdown"]["location"] == 1.0 and r["breakdown"]["work_type"] == 1.0
    assert 0 < r["score"] <= 100
    # unknown factors are excluded, not treated as zero
    r2 = score_internship(user(skills=[]), mk(skills=[], city=None, work_type=None), W)
    assert r2["breakdown"]["skills"] is None and r2["breakdown"]["location"] is None
    assert r2["score"] == 100.0 * (r2["breakdown"]["interest"])  # only interest scored
    # better skill match ranks higher
    assert score_internship(user(skills=["Python", "SQL"]), mk(), W)["score"] > r["score"]


def test_remote_ignores_city_and_eligibility_is_separate():
    r = score_internship(user(location="Pune"), mk(work_type="remote", city=None), W)
    assert r["breakdown"]["location"] == 1.0
    ok = score_internship(user(), mk(grad_years=[2026, 2027]), W)["eligibility"]
    bad = score_internship(user(graduation_year=2029), mk(grad_years=[2026, 2027]), W)["eligibility"]
    unk = score_internship(user(graduation_year=None), mk(grad_years=[2026]), W)["eligibility"]
    assert (ok["status"], bad["status"], unk["status"]) == ("eligible", "not_eligible", "unknown")
