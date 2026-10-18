"""End-to-end API tests (needs the packages in requirements.txt)."""
import os
import tempfile
from datetime import datetime, timedelta, timezone

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["ADMIN_API_KEY"] = "secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.importer import run_import  # noqa: E402
from app.services.sources import ListSource  # noqa: E402


def _iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


RECORDS = [
    dict(external_id="1", title="Python Backend Intern", company="Acme", location="Hyderabad",
         description="Build APIs with Python, Django and SQL.", application_url="https://acme.com/j/1?utm_source=x",
         deadline=_iso(30), stipend="₹15,000/month", duration="3 months"),
    dict(external_id="2", title="Data Analyst Intern", company="Beta", location="Remote",
         description="Excel, Tableau, SQL.", application_url="https://beta.io/j/2", deadline=_iso(3)),
    dict(external_id="3", title="Old Frontend Intern", company="Gamma", location="Pune",
         description="React and CSS.", application_url="https://gamma.dev/j/3", deadline=_iso(-5)),
    dict(external_id="4", title="Senior Engineer", company="Delta", application_url="https://delta.com/4"),  # rejected
    dict(external_id="5", title="Cloud Intern", company="Eps", description="AWS", application_url="ftp://bad"),  # rejected
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        db = SessionLocal()
        run = run_import(db, ListSource("test", RECORDS))
        assert (run.created, run.rejected, run.status) == (3, 2, "success")
        db.close()
        yield c


def test_reimport_creates_no_duplicates(client):
    db = SessionLocal()
    run = run_import(db, ListSource("test", RECORDS))
    assert run.created == 0 and run.unchanged == 3
    # same opportunity from another source -> duplicate, not a new row
    other = [dict(RECORDS[0], external_id="zz", application_url="https://aggregator.com/xyz")]
    assert run_import(db, ListSource("other", other)).duplicates == 1
    db.close()
    assert client.get("/api/internships?include_expired=true").json()["total"] == 3


def test_failed_source_is_reported_not_faked(client):
    class Broken:
        name = "broken"

        def fetch(self):
            raise ConnectionError("source down")

    db = SessionLocal()
    run = run_import(db, Broken())
    db.close()
    assert run.status == "failed" and "source down" in run.error and run.created == 0


def test_search_filters_and_status(client):
    r = client.get("/api/internships").json()
    assert r["total"] == 2  # expired hidden by default
    by_title = {i["title"]: i for i in r["items"]}
    assert by_title["Data Analyst Intern"]["status"] == "closing_soon"
    assert by_title["Python Backend Intern"]["status"] == "open"
    assert "stipend" in by_title["Data Analyst Intern"]["missing_fields"]
    assert "deadline" not in by_title["Data Analyst Intern"]["missing_fields"]
    assert client.get("/api/internships?skills=python").json()["total"] == 1
    assert client.get("/api/internships?work_type=remote").json()["total"] == 1
    assert client.get("/api/internships?location=hyderabad").json()["total"] == 1
    assert client.get("/api/internships?status=expired").json()["total"] == 1
    assert client.get("/api/internships?min_stipend=10000").json()["total"] == 1
    assert client.get("/api/internships?q=100%25").json()["total"] == 0  # % is escaped, not a wildcard


def test_profile_validation_and_recommendations(client):
    uid = client.post("/api/users", json={"full_name": "Asha"}).json()["id"]
    h = {"X-User-Id": str(uid)}
    assert client.get("/api/recommendations").status_code == 401
    assert client.put("/api/profile", headers=h, json={"skills": ["Underwater Basket Weaving"]}).status_code == 422
    assert client.put("/api/profile", headers=h, json={"location": "Atlantis"}).status_code == 422
    ok = client.put("/api/profile", headers=h, json={
        "location": "Hyderabad", "skills": ["python", "SQL", "django"], "work_types": ["onsite"],
        "desired_roles": ["Backend Developer Intern"], "graduation_year": 2027})
    assert ok.status_code == 200 and ok.json()["skills"] == ["Django", "Python", "SQL"]
    recs = client.get("/api/recommendations", headers=h).json()
    assert recs["items"][0]["internship"]["title"] == "Python Backend Intern"
    top = recs["items"][0]
    assert top["score"] > recs["items"][-1]["score"] and top["matched_skills"] and top["reasons"]
    assert all(i["internship"]["status"] != "expired" for i in recs["items"])


def test_saved_is_per_user(client):
    a = {"X-User-Id": str(client.post("/api/users", json={}).json()["id"])}
    b = {"X-User-Id": str(client.post("/api/users", json={}).json()["id"])}
    iid = client.get("/api/internships").json()["items"][0]["id"]
    assert client.put(f"/api/saved/{iid}", headers=a).status_code == 204
    assert client.put(f"/api/saved/{iid}", headers=a).status_code == 204  # idempotent
    assert len(client.get("/api/saved", headers=a).json()) == 1
    assert client.get("/api/saved", headers=b).json() == []
    assert client.put("/api/saved/99999", headers=a).status_code == 404
    assert client.delete(f"/api/saved/{iid}", headers=a).status_code == 204
    assert client.get("/api/saved", headers=a).json() == []


def test_admin_requires_key_and_meta_suggestions(client):
    assert client.post("/api/admin/refresh-status").status_code == 401
    assert client.post("/api/admin/refresh-status", headers={"X-Admin-Key": "secret"}).status_code == 200
    assert "Bengaluru" in client.get("/api/meta/locations?q=bang").json()
    assert "Python" in client.get("/api/meta/skills?q=pyth").json()


# ---------------- Part 1: closure sync + admin discovery endpoints ----------------
class _Board(ListSource):
    complete_listing = True


def _board_rec(i, **kw):
    return dict(external_id=f"b{i}", title=f"Cloud Intern {i}", company="Board Co", location="Pune",
                description="AWS and Linux", application_url=f"https://boardco.example/jobs/{i}", **kw)


def test_complete_board_closes_vanished_listings(client):
    db = SessionLocal()
    run_import(db, _Board("greenhouse:boardco", [_board_rec(1), _board_rec(2)]))
    listed = {i["title"]: i for i in client.get("/api/internships?q=Cloud Intern").json()["items"]}
    assert listed["Cloud Intern 1"]["status"] == "open" and listed["Cloud Intern 2"]["status"] == "open"
    run_import(db, _Board("greenhouse:boardco", [_board_rec(1)]))  # role 2 was taken down by the company
    db.close()
    titles = [i["title"] for i in client.get("/api/internships?q=Cloud Intern").json()["items"]]
    assert titles == ["Cloud Intern 1"]
    gone = [i for i in client.get("/api/internships?q=Cloud Intern&include_expired=true").json()["items"] if i["title"] == "Cloud Intern 2"]
    assert gone and gone[0]["status"] == "expired"


def test_failed_complete_source_closes_nothing(client):
    class Down(_Board):
        def fetch(self):
            raise ConnectionError("board down")

    db = SessionLocal()
    assert run_import(db, Down("greenhouse:boardco", [])).status == "failed"
    db.close()
    assert [i["title"] for i in client.get("/api/internships?q=Cloud Intern").json()["items"]] == ["Cloud Intern 1"]


def test_admin_sources_test_and_coverage(client):
    h = {"X-Admin-Key": "secret"}
    assert client.get("/api/admin/sources").status_code == 401
    assert client.get("/api/admin/sources", headers=h).json()["sources"] is not None
    assert client.post("/api/admin/sources/test?name=nope", headers=h).status_code == 404
    cov = client.get("/api/admin/coverage", headers=h).json()
    assert cov["open_total"] >= 1 and "open_by_evidence" in cov and cov["by_source"]
    assert client.get("/api/admin/runs", headers=h).json()[0]["source"]
