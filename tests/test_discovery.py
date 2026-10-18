"""Part 1 (discovery) tests. No database and no network: HTTP is served by httpx.MockTransport."""
import json
from contextlib import contextmanager
from datetime import datetime, timedelta

import httpx
import pytest

from app.config import settings
from app.services import pagecheck
from app.services.geo import in_india_scope
from app.services.normalize import Reject, normalize_record
from app.services.preview import preview_source
from app.services.sources import (
    ListSource, build_sources, load_sources, net,
)
from app.services.sources.adzuna import AdzunaSource
from app.services.sources.ats import AshbySource, GreenhouseSource, LeverSource
from app.services.sources.mappers import parse_feed, parse_sitemap
from app.services.sources.web import JobPostingPagesSource, PoliteFetcher
from app.tools import discover_boards as db_tool


@contextmanager
def served(handler):
    """Route every HTTP call through `handler(request) -> httpx.Response` (no sleeping, public hosts)."""
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    old = (net._sleep, net.is_public_host, settings.crawl_delay_seconds)
    net._sleep, net.is_public_host, settings.crawl_delay_seconds = (lambda s: None), (lambda h: True), 0
    net.set_transport(httpx.MockTransport(wrapped))
    try:
        yield calls
    finally:
        net.set_transport(None)
        net._sleep, net.is_public_host, settings.crawl_delay_seconds = old


# ---------------- network layer ----------------
def test_retries_transient_errors_then_succeeds():
    state = {"n": 0}

    def h(req):
        state["n"] += 1
        return httpx.Response(503) if state["n"] < 3 else httpx.Response(200, json={"ok": 1})

    with served(h) as calls:
        assert net.get_json("https://api.test/x") == {"ok": 1}
    assert len(calls) == 3


def test_404_is_not_retried_and_secrets_never_leak():
    with served(lambda r: httpx.Response(404)) as calls:
        with pytest.raises(net.FetchError) as e:
            net.get_json("https://api.test/x", params={"app_key": "TOPSECRET"})
    assert len(calls) == 1 and e.value.status == 404 and "TOPSECRET" not in str(e.value)

    with served(lambda r: httpx.Response(500)):
        with pytest.raises(net.FetchError) as e:
            net.get_json("https://api.test/x?token=TOPSECRET", params={"app_key": "TOPSECRET"})
    assert "TOPSECRET" not in str(e.value) and "attempt" in str(e.value)
    assert net.redact_text("GET https://a/b?app_key=abc123&x=1 failed") == "GET https://a/b?app_key=***&x=1 failed"


def test_retry_after_is_honoured():
    sleeps, n = [], {"n": 0}

    def h(req):
        n["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "7"}) if n["n"] == 1 else httpx.Response(200, json=[])

    with served(h):
        net._sleep = sleeps.append
        net.get_json("https://api.test/x")
    assert sleeps == [7.0]


# ---------------- ATS sources ----------------
GH_LIST = {"jobs": [
    {"id": 101, "title": "Software Engineer Intern", "location": {"name": "Bengaluru, India"}, "absolute_url": "https://boards.greenhouse.io/acme/jobs/101"},
    {"id": 102, "title": "Data Science Intern", "location": {"name": "Remote - India"}, "absolute_url": "https://boards.greenhouse.io/acme/jobs/102"},
    {"id": 103, "title": "Senior Staff Engineer", "location": {"name": "Bengaluru"}, "absolute_url": "https://boards.greenhouse.io/acme/jobs/103"},
]}


def gh_handler(fail_detail=False):
    def h(req):
        path = req.url.path
        if path == "/v1/boards/acme":
            return httpx.Response(200, json={"name": "Acme Corp"})
        if path == "/v1/boards/acme/jobs":
            assert "content" not in req.url.params, "the board list must be fetched WITHOUT descriptions"
            return httpx.Response(200, json=GH_LIST)
        if path.startswith("/v1/boards/acme/jobs/"):
            if fail_detail:
                return httpx.Response(500)
            jid = path.rsplit("/", 1)[1]
            title = next(j["title"] for j in GH_LIST["jobs"] if str(j["id"]) == jid)
            return httpx.Response(200, json={"id": int(jid), "title": title, "content": "&lt;p&gt;Build things with Python &amp;amp; SQL&lt;/p&gt;",
                                              "location": {"name": "Bengaluru, India"}, "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{jid}"})
        return httpx.Response(404)
    return h


def test_greenhouse_fetches_details_only_for_internships():
    with served(gh_handler()) as calls:
        out = list(GreenhouseSource("acme").fetch())
    detail_calls = [c.url.path for c in calls if c.url.path.count("/") == 5]
    assert sorted(detail_calls) == ["/v1/boards/acme/jobs/101", "/v1/boards/acme/jobs/102"]  # not the Staff Engineer
    assert [o["title"] for o in out] == ["Software Engineer Intern", "Data Science Intern"]
    assert all(o["company"] == "Acme Corp" for o in out)
    rec = normalize_record(out[0], "greenhouse:acme", True)
    assert {"Python", "SQL"} <= set(rec["skills"]) and "<" not in rec["description"]


def test_greenhouse_detail_failure_keeps_the_listing():
    with served(gh_handler(fail_detail=True)):
        out = list(GreenhouseSource("acme", "Acme").fetch())
    assert len(out) == 2 and not any(o.get("description") for o in out)  # still listed, so still counted as open


def test_lever_includes_requirement_lists_and_guards_paging():
    page = [{"id": f"id{i}", "text": "ML Intern" if i % 2 == 0 else "Engineer", "categories": {"location": "Mumbai", "commitment": "Intern" if i % 2 == 0 else "Full-time"},
             "descriptionPlain": "Desc", "lists": [{"text": "Requirements", "content": "<li>PyTorch</li>"}], "hostedUrl": f"https://jobs.lever.co/x/id{i}",
             "applyUrl": f"https://jobs.lever.co/x/id{i}/apply"} for i in range(100)]
    with served(lambda r: httpx.Response(200, json=page)) as calls:  # server ignores skip/limit and repeats the page
        out = list(LeverSource("x").fetch())
    assert len(calls) == 2 and len(out) == 50  # second identical page detected and dropped, no duplicates
    assert "PyTorch" in out[0]["description"]


def test_ashby_skips_unlisted_and_non_interns():
    data = {"jobs": [
        {"id": "a", "title": "Design Intern", "location": "Bengaluru", "employmentType": "Intern", "jobUrl": "https://jobs.ashbyhq.com/z/a", "isListed": True},
        {"id": "b", "title": "Hidden Intern", "jobUrl": "https://jobs.ashbyhq.com/z/b", "isListed": False},
        {"id": "c", "title": "Product Designer", "employmentType": "FullTime", "jobUrl": "https://jobs.ashbyhq.com/z/c"},
        {"id": "d", "title": "Product Analyst", "employmentType": "Intern", "jobUrl": "https://jobs.ashbyhq.com/z/d"},  # intern by type only
    ]}
    with served(lambda r: httpx.Response(200, json=data)):
        out = list(AshbySource("z", "Zed").fetch())
    assert [o["title"] for o in out] == ["Design Intern", "Product Analyst"]


# ---------------- Adzuna ----------------
def test_adzuna_maps_results_and_never_leaks_keys():
    def h(req):
        assert req.url.params["app_key"] == "KEY" and req.url.path.startswith("/v1/api/jobs/in/search/")
        return httpx.Response(200, json={"results": [
            {"id": "1", "title": "Python Intern", "company": {"display_name": "Acme"}, "location": {"display_name": "Pune, Maharashtra"},
             "redirect_url": "https://www.adzuna.in/land/ad/1", "description": "snippet", "salary_min": 1, "salary_is_predicted": "1"},
            {"id": "2", "title": "Sales Manager", "redirect_url": "https://www.adzuna.in/land/ad/2"},
        ]})

    src = AdzunaSource({"app_id": "ID", "app_key": "KEY", "queries": ["intern"], "pages": 1})
    with served(h):
        out = list(src.fetch())
    assert len(out) == 1 and out[0]["company"] == "Acme" and "stipend" not in out[0]

    with served(lambda r: httpx.Response(500)):
        with pytest.raises(net.FetchError) as e:
            list(src.fetch())
    assert "KEY" not in str(e.value)
    with pytest.raises(ValueError):
        list(AdzunaSource({"app_id": "", "app_key": ""}).fetch())


# ---------------- web: robots, sitemaps, JSON-LD ----------------
def _jobpage(title, valid_through="2099-01-01"):
    ld = {"@context": "https://schema.org", "@type": "JobPosting", "title": title, "description": "<p>Python and SQL</p>",
          "hiringOrganization": {"@type": "Organization", "name": "Acme"}, "employmentType": "INTERN", "validThrough": valid_through,
          "jobLocation": {"@type": "Place", "address": {"addressLocality": "Hyderabad", "addressCountry": "IN"}}}
    return f'<html><head><script type="application/ld+json">{json.dumps(ld)}</script></head><body>x</body></html>'


def test_polite_fetcher_obeys_robots_and_refuses_unsafe_hosts():
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    with served(h) as calls:
        f = PoliteFetcher()
        assert f.get("https://careers.test/jobs/1") == "<html>ok</html>"
        assert f.get("https://careers.test/private/2") is None
        assert not any(c.url.path == "/private/2" for c in calls)  # never even requested
        assert f.get("http://localhost/x") is None and f.get("ftp://careers.test/x") is None

    with served(lambda r: httpx.Response(503)):  # robots.txt unreadable -> no permission -> no fetch
        assert PoliteFetcher().get("https://other.test/jobs") is None

    def redirect(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.host == "a.test":
            return httpx.Response(302, headers={"location": "https://evil.test/x"})
        return httpx.Response(200, text="secret", headers={"content-type": "text/html"})

    with served(redirect):
        assert PoliteFetcher().get("https://a.test/go") is None  # redirect left the host

    old = net.is_public_host
    net.is_public_host = lambda h: False
    try:
        with served(lambda r: httpx.Response(200, text="x", headers={"content-type": "text/html"})) as calls:
            net.is_public_host = lambda h: False
            assert PoliteFetcher().get("https://internal.corp/x") is None and not calls
    finally:
        net.is_public_host = old


def test_sitemap_discovery_finds_internship_pages():
    index = '<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://c.test/sm-jobs.xml</loc></sitemap><sitemap><loc>https://evil.test/sm.xml</loc></sitemap></sitemapindex>'
    jobs = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://c.test/jobs/intern-python</loc></url><url><loc>https://c.test/jobs/director</loc></url></urlset>'

    def h(req):
        p = req.url.path
        if p == "/robots.txt":
            return httpx.Response(404)
        if p == "/sitemap.xml":
            return httpx.Response(200, text=index, headers={"content-type": "application/xml"})
        if p == "/sm-jobs.xml":
            return httpx.Response(200, text=jobs, headers={"content-type": "application/xml"})
        if p == "/jobs/intern-python":
            return httpx.Response(200, text=_jobpage("Python Intern"), headers={"content-type": "text/html"})
        return httpx.Response(404)

    src = JobPostingPagesSource({"name": "c", "sitemaps": ["https://c.test/sitemap.xml"]})
    with served(h) as calls:
        out = list(src.fetch())
    assert [o["title"] for o in out] == ["Python Intern"]
    assert not any(c.url.host == "evil.test" for c in calls)  # cross-host sitemap entries are ignored
    assert not any(c.url.path == "/jobs/director" for c in calls)  # url_pattern default 'intern'
    rec = normalize_record(out[0], "web:c", True)
    assert rec["city"] == "Hyderabad" and rec["deadline"] is not None


def test_sitemap_and_feed_parsers_refuse_entity_bombs():
    with pytest.raises(ValueError):
        parse_sitemap('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><urlset/>')
    with pytest.raises(ValueError):
        parse_feed('<!DOCTYPE x [<!ENTITY a "b">]><rss/>')
    pages, children = parse_sitemap('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc> https://a.test/x </loc></url></urlset>')
    assert pages == ["https://a.test/x"] and children == []


def test_web_source_fails_loudly_when_nothing_is_readable():
    with served(lambda r: httpx.Response(503)):
        with pytest.raises(RuntimeError, match="no page could be fetched"):
            list(JobPostingPagesSource({"name": "c", "pages": ["https://c.test/careers"]}).fetch())


# ---------------- closed-page detection ----------------
def test_closed_pages_are_detected_conservatively():
    now = datetime(2026, 10, 14)
    assert pagecheck.classify_page(_jobpage("X", "2020-01-01"), now) is False  # structured data says expired
    assert pagecheck.classify_page(_jobpage("X", "2099-01-01"), now) is None
    assert pagecheck.classify_page("<html><title>Careers</title><body><h1>Sorry, this position has been filled.</h1></body></html>", now) is False
    assert pagecheck.classify_page("<html><body>Applications are now closed for this internship.</body></html>", now) is False
    assert pagecheck.classify_page("<html><body><h1>Python Intern</h1><p>Apply now! We are hiring.</p></body></html>", now) is None
    # a live structured posting beats boilerplate that merely mentions closed roles
    live = _jobpage("X").replace("<body>x</body>", "<body>Other roles are no longer available</body>")
    assert pagecheck.classify_page(live, now) is None


# ---------------- India scope ----------------
@pytest.mark.parametrize("loc,ok", [
    ("Bengaluru, India", True), ("Pune", True), ("Hyderabad, Telangana", True), ("Karnataka", True),
    ("Remote", True), ("Remote - India", True), ("Remote (APAC)", True), ("Worldwide", True),
    ("Remote - US", False), ("Remote, United Kingdom", False), ("Remote (EMEA)", False),
    ("San Francisco, CA", False), ("London", False), ("Singapore", False),
    ("", True), (None, True), ("Multiple locations", True),
])
def test_in_india_scope(loc, ok):
    assert in_india_scope(loc) is ok


def test_normalize_applies_scope_and_wider_intern_titles():
    base = dict(title="Python Intern", company="A", application_url="https://a.test/1", description="Python")
    with pytest.raises(Reject, match="outside_india"):
        normalize_record({**base, "location": "Remote - US", "work_type": "remote"}, "s", True)
    assert normalize_record({**base, "location": "Remote - US"}, "s", False)["work_type"] == "remote"
    assert normalize_record({**base, "title": "Summer Analyst", "location": "Mumbai"}, "s", True)["city"] == "Mumbai"
    assert normalize_record({**base, "title": "Backend Co-op", "location": "Pune"}, "s", True)["city"] == "Pune"


# ---------------- registry / config ----------------
def test_registry_validates_and_reports_config_problems(tmp_path):
    cfg = {"sources": [
        {"type": "greenhouse", "boards": ["acme", {"token": "beta", "company": "Beta Inc"}]},
        {"type": "lever", "companies": ["../evil"]},                 # path-injection attempt
        {"type": "ashby"},                                           # missing boards
        {"type": "nope", "boards": ["x"]},                           # unknown type
        {"type": "rss", "name": "off", "url": "https://x.test/f", "enabled": False},
        {"type": "json_feed", "name": "p", "url": "https://x.test", "field_map": {"title": "t"}, "headers": {"A": "${INTERNRADAR_NOPE}"}},
        {"type": "jobposting_pages", "name": "w"},                   # needs pages or sitemaps
    ]}
    f = tmp_path / "sources.json"
    f.write_text(json.dumps(cfg))
    old = settings.sources_file
    settings.sources_file = str(f)
    try:
        sources, errors = load_sources()
    finally:
        settings.sources_file = old
    assert [s.name for s in sources] == ["greenhouse:acme", "greenhouse:beta"]
    assert len(errors) == 5 and not any("evil" in e and "Bearer" in e for e in errors)
    assert any("INTERNRADAR_NOPE" in e for e in errors) and any("invalid board token" in e for e in errors)
    assert [s.kind for s in build_sources({"type": "lever", "companies": ["a"], "region": "eu"})] == ["lever"]
    assert build_sources({"type": "lever", "companies": ["a"], "region": "eu"})[0].host == "api.eu.lever.co"


def test_complete_listing_flags():
    assert GreenhouseSource("a").complete_listing and LeverSource("a").complete_listing and AshbySource("a").complete_listing
    assert not AdzunaSource({"app_id": "a", "app_key": "b"}).complete_listing
    assert not JobPostingPagesSource({"name": "w", "pages": ["https://a.test"]}).complete_listing
    assert not ListSource("x", []).complete_listing


# ---------------- dry-run preview ----------------
def test_preview_shows_what_would_be_imported_and_why_not():
    recs = [
        dict(title="Python Intern", company="A", location="Pune", description="Python, SQL", application_url="https://a.test/1", deadline="2099-01-01"),
        dict(title="Data Intern", company="A", location="Austin, TX", application_url="https://a.test/2"),
        dict(title="CEO", company="A", application_url="https://a.test/3"),
        dict(title="Cloud Intern", company="A", application_url="not a url"),
    ]
    out = preview_source(ListSource("t", recs), sample=5)
    assert (out["fetched"], out["accepted"], out["rejected"]) == (4, 1, 3)
    assert out["reject_reasons"] == {"outside_india": 1, "not_internship": 1, "invalid_application_url": 1}
    assert out["quality"]["with_deadline"] == 1 and out["sample"][0]["city"] == "Pune"
    assert {r["reason"] for r in out["sample_rejected"]} == set(out["reject_reasons"])

    class Down:
        name, kind = "down", "x"

        def fetch(self):
            raise ConnectionError("boom app_key=SECRET")

    bad = preview_source(Down())
    assert "boom" in bad["error"] and "SECRET" not in bad["error"] and bad["fetched"] == 0


# ---------------- board discovery tool ----------------
def test_slug_variants():
    assert db_tool.slug_variants("Pine Labs") == ["pinelabs", "pine-labs", "pine"]  # generic word stripped as a last guess
    assert db_tool.slug_variants("Razorpay") == ["razorpay"]
    assert db_tool.slug_variants("BYJU'S")[0] == "byjus" and db_tool.slug_variants("Fi") == []
    assert db_tool.slug_variants("Yellow.ai") == ["yellow"] and db_tool.slug_variants("Acme Technologies") == ["acmetechnologies", "acme-technologies", "acme"]


def test_discover_finds_boards_and_merges_sources_json():
    def h(req):
        host, path = req.url.host, req.url.path
        if host == "boards-api.greenhouse.io" and path == "/v1/boards/acmelabs/jobs":
            return httpx.Response(200, json=GH_LIST)
        if host == "boards-api.greenhouse.io" and path == "/v1/boards/acmelabs":
            return httpx.Response(200, json={"name": "Acme Labs"})
        if host == "api.lever.co" and path == "/v0/postings/acme-labs":
            return httpx.Response(200, json=[])  # empty list: indistinguishable from unknown -> not claimed
        return httpx.Response(404)

    with served(h):
        found = db_tool.discover(["Acme Labs", "Nobody Inc"], workers=2)
    assert len(found) == 1
    f = found[0]
    assert (f["ats"], f["slug"], f["jobs"], f["interns"], f["india_interns"]) == ("greenhouse", "acmelabs", 3, 2, 2)

    cfg = db_tool.merge_sources({"sources": [{"type": "greenhouse", "boards": ["acmelabs", "keep"]}, {"type": "rss", "name": "r", "url": "https://x"}]}, found)
    gh = [s for s in cfg["sources"] if s["type"] == "greenhouse"]
    assert len(gh) == 1 and gh[0]["boards"] == ["acmelabs", "keep"]  # no duplicate added, existing entries untouched
    cfg2 = db_tool.merge_sources({}, found)
    assert cfg2["sources"] == [{"type": "greenhouse", "boards": [{"token": "acmelabs", "company": "Acme Labs"}]}]


def test_company_list_is_clean():
    import pathlib

    names = [l.strip() for l in pathlib.Path("data/india_companies.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]
    assert len(names) == len({n.lower() for n in names}) > 100
