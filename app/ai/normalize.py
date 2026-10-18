"""Turn a raw source record into the platform's standard internship dict.
Pure functions only (no DB / framework imports)."""
import hashlib
import html
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as dtparser

from .geo import in_india_scope, normalize_city
from .skills import canonical_skill, extract_skills, skills_blob

IST = timezone(timedelta(hours=5, minutes=30))
INTERN_RE = re.compile(
    r"\b(interns?|internships?|trainees?|apprentice(?:ship)?s?|co-?ops?|summer (?:analyst|associate)s?)\b", re.I
)


class Reject(Exception):
    """Record cannot be accepted; message is the reason code."""


# ---------- text / url ----------
def clean_text(value) -> str:
    if value is None:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", str(value))
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def canonical_url(url) -> str | None:
    """Validated, tracking-stripped URL used as a dedup key. None if unusable."""
    if not url:
        return None
    try:
        p = urlsplit(str(url).strip())
        host = (p.hostname or "").lower()
        port = p.port
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not host:
        return None
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return None
    try:
        if not ipaddress.ip_address(host).is_global:
            return None
    except ValueError:
        if "." not in host:
            return None
    q = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not (k.lower().startswith("utm_") or k.lower() in {"gclid", "fbclid", "ref"})
    ]
    netloc = host + (f":{port}" if port and port not in (80, 443) else "")
    return urlunsplit((p.scheme, netloc, p.path.rstrip("/") or "/", urlencode(q), ""))


# ---------- structured fields ----------
def parse_stipend(text) -> tuple[int | None, int | None]:
    """Monthly INR (min, max) when clearly parseable; (0, 0) for unpaid; else (None, None)."""
    if text is None or text == "":
        return None, None
    t = str(text).lower().replace(",", "")
    if re.search(r"\bunpaid\b|\bno stipend\b", t):
        return 0, 0
    if re.search(r"\$|€|£|\b(usd|eur|gbp|cad|aud|sgd|aed|cny|jpy|chf)\b", t):
        return None, None
    if re.search(r"per (hour|week|day)|/\s*(hr|hour|week|wk|day)\b|hourly|weekly|daily", t):
        return None, None  # not a monthly figure; don't misread it as one
    nums = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(k|lpa|lakhs?|lacs?)?", t):
        v = float(m.group(1))
        unit = m.group(2)
        if unit == "k":
            v *= 1000
        elif unit:
            v *= 100000
        nums.append(v)
    nums = nums[:2]
    if not nums:
        return None, None
    lo, hi = min(nums), max(nums)
    if re.search(r"per year|/year|/yr|annum|yearly|lpa", t):
        lo, hi = lo / 12, hi / 12
    if hi < 500 or hi > 10_000_000:
        return None, None
    return int(lo), int(hi)


def parse_duration(text) -> float | None:
    if not text:
        return None
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|–|to)?\s*(\d+(?:\.\d+)?)?\s*(month|week|year)s?", str(text).lower()
    )
    if not m:
        return None
    n = max(float(m.group(1)), float(m.group(2) or 0))
    months = {"month": n, "week": n / 4.345, "year": n * 12}[m.group(3)]
    return round(months, 1) if 0 < months <= 24 else None


def parse_deadline(value) -> datetime | None:
    """-> naive UTC datetime. Date-only values mean end of that day (IST)."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 1e11 else value
            dt = datetime.fromtimestamp(ts, timezone.utc)
        else:
            s = str(value).strip()
            dt = dtparser.parse(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)
            if not re.search(r"\d{1,2}:\d{2}", s):
                dt = dt.replace(hour=23, minute=59, second=59)
    except (ValueError, OverflowError, OSError):
        return None
    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt if 2000 <= dt.year <= 2100 else None


def detect_work_type(explicit, location, title, description) -> str | None:
    for blob in (explicit, location, title):
        b = (str(blob) if blob else "").lower()
        if not b:
            continue
        if "hybrid" in b:
            return "hybrid"
        if re.search(r"\bremote\b|work from home|\bwfh\b|\banywhere\b|worldwide", b):
            return "remote"
        if re.search(r"on-?site|in-?office|\bin office\b", b):
            return "onsite"
    head = (description or "")[:600].lower()
    if "hybrid" in head:
        return "hybrid"
    if re.search(r"work from home|fully remote|100% remote|remote internship", head):
        return "remote"
    if normalize_city(location):
        return "onsite"
    return None


def extract_grad_years(text: str) -> list[int]:
    """Graduation/batch years only when stated next to batch/graduation wording."""
    years: set[int] = set()
    pat = r"(?:batch|graduat\w*|pass(?:ing)?[- ]?out|class of)[^.\n]{0,40}?((?:20\d{2})(?:\s*(?:,|/|&|and|or|-|–|to)\s*20\d{2})*)"
    for m in re.finditer(pat, text or "", re.I):
        ys = [int(y) for y in re.findall(r"20\d{2}", m.group(1))]
        if len(ys) == 2 and re.search(r"-|–|\bto\b", m.group(1)) and 0 < ys[1] - ys[0] <= 4:
            ys = list(range(ys[0], ys[1] + 1))
        years.update(ys)
    return sorted(years)


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fingerprint(title: str, company: str, city: str | None, work_type: str | None) -> str:
    t = re.sub(r"\b(interns?|internships?|trainees?)\b", "", title, flags=re.I)
    place = city or ("remote" if work_type == "remote" else "")
    raw = f"{_norm_key(t)}|{_norm_key(company)}|{_norm_key(place)}"
    return hashlib.sha1(raw.encode()).hexdigest()


# ---------- main entry ----------
def normalize_record(raw: dict, source_name: str, india_only: bool = False) -> dict:
    title = clean_text(raw.get("title"))[:300]
    company = clean_text(raw.get("company"))[:200]
    if not title:
        raise Reject("missing_title")
    if not company:
        raise Reject("missing_company")
    if not (INTERN_RE.search(title) or INTERN_RE.search(str(raw.get("job_type") or ""))):
        raise Reject("not_internship")

    app_raw = str(raw.get("application_url") or "").strip()
    url_key = canonical_url(app_raw)
    if not url_key:
        raise Reject("invalid_application_url")

    description = clean_text(raw.get("description"))[:20000] or None
    location = clean_text(raw.get("location"))[:200] or None
    city = normalize_city(location)
    work_type = detect_work_type(raw.get("work_type"), location, title, description)
    # India first: a stated place outside India (incl. remote roles limited to another country) is out of scope
    if india_only and not in_india_scope(location):
        raise Reject("outside_india")

    # skills: explicit list from source (validated against vocab) + extracted from text
    given = raw.get("skills") or []
    if isinstance(given, str):
        given = re.split(r"[,;|/]", given)
    skills = {canonical_skill(str(s)) for s in given} - {None}
    skills |= set(extract_skills(f"{title}\n{description or ''}"))
    skills_list = sorted(skills)

    eligibility = clean_text(raw.get("eligibility"))[:2000] or None
    grad_years = extract_grad_years(f"{eligibility or ''}\n{(description or '')[:2000]}")

    stipend_text = clean_text(raw.get("stipend"))[:200] or None
    smin, smax = parse_stipend(stipend_text)
    duration_text = clean_text(raw.get("duration"))[:100] or None
    deadline = parse_deadline(raw.get("deadline"))

    website = canonical_url(raw.get("company_website"))
    source_url = canonical_url(raw.get("source_url"))
    ext = raw.get("external_id")

    return {
        "fingerprint": fingerprint(title, company, city, work_type),
        "apply_url_key": url_key[:1000],
        "source_name": source_name,
        "external_id": str(ext)[:200] if ext not in (None, "") else None,
        "source_url": source_url,
        "title": title,
        "company": company,
        "company_website": website,
        "description": description,
        "skills": skills_list,
        "skills_blob": skills_blob(skills_list),
        "eligibility": eligibility,
        "grad_years": grad_years,
        "location": location,
        "city": city,
        "work_type": work_type,
        "stipend_text": stipend_text,
        "stipend_min": smin,
        "stipend_max": smax,
        "duration_text": duration_text,
        "duration_months": parse_duration(duration_text),
        "deadline": deadline,
        "application_url": app_raw[:1000],
        "validation_status": "complete" if (description and (skills_list or deadline)) else "partial",
    }
