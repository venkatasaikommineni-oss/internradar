"""Pure parsing / field-mapping helpers for each source type (no network, no DB)."""
import html
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


def _s(v) -> str:
    """Best-effort string from str | {'name': ..} | list."""
    if v is None:
        return ""
    if isinstance(v, dict):
        return _s(v.get("name") or v.get("value") or "")
    if isinstance(v, (list, tuple)):
        return ", ".join(x for x in (_s(i) for i in v) if x)
    return str(v).strip()


def salary_text(lo, hi, currency, interval) -> str | None:
    """'INR 10000-15000 per month' - the normaliser only trusts monthly INR figures."""
    vals = []
    for x in (lo, hi):
        if x in (None, ""):
            continue
        try:
            vals.append(str(int(float(x))))
        except (TypeError, ValueError):
            return None
    if not vals:
        return None
    iv = str(interval or "").lower()
    per = " per month" if "month" in iv else " per year" if ("year" in iv or "annual" in iv) else \
        f" per {iv.strip('-_ ')}" if iv else ""
    return f"{(currency or 'INR').upper()} {'-'.join(dict.fromkeys(vals))}{per}"


# ---------- ATS public job-board APIs ----------
def greenhouse_to_raw(j: dict) -> dict:
    loc = j.get("location") or {}
    url = j.get("absolute_url")
    return {
        "external_id": j.get("id"),
        "title": j.get("title"),
        # Greenhouse returns the description HTML-escaped
        "description": html.unescape(j.get("content") or ""),
        "location": loc.get("name") if isinstance(loc, dict) else _s(loc),
        "application_url": url,
        "source_url": url,
    }


def lever_to_raw(p: dict) -> dict:
    cats = p.get("categories") or {}
    sr = p.get("salaryRange") or {}
    # the responsibilities / requirements bullet lists live in `lists` (HTML) - that is
    # where most required skills are named, so they must be part of the description
    lists = "\n".join(
        f"{l.get('text') or ''}\n{l.get('content') or ''}" for l in (p.get("lists") or []) if isinstance(l, dict)
    )
    desc = "\n\n".join(x for x in (p.get("descriptionPlain"), lists, p.get("additionalPlain")) if x) or p.get("description")
    return {
        "external_id": p.get("id"),
        "title": p.get("text"),
        "description": desc,
        "location": cats.get("location") or _s(p.get("allLocations")),
        "job_type": cats.get("commitment"),
        "work_type": p.get("workplaceType"),
        "stipend": salary_text(sr.get("min"), sr.get("max"), sr.get("currency"), sr.get("interval")),
        "application_url": p.get("applyUrl") or p.get("hostedUrl"),
        "source_url": p.get("hostedUrl"),
    }


def ashby_to_raw(j: dict) -> dict:
    comp = j.get("compensation") or {}
    return {
        "external_id": j.get("id"),
        "title": j.get("title"),
        "description": j.get("descriptionPlain") or j.get("descriptionHtml"),
        "location": j.get("location"),
        "job_type": j.get("employmentType"),
        "work_type": "remote" if j.get("isRemote") else None,
        "stipend": comp.get("compensationTierSummary") if isinstance(comp, dict) else None,
        "application_url": j.get("applyUrl") or j.get("jobUrl"),
        "source_url": j.get("jobUrl"),
    }


def adzuna_to_raw(r: dict) -> dict:
    """Adzuna returns a description *snippet* and may predict salaries, so no stipend is taken."""
    loc = r.get("location") or {}
    comp = r.get("company") or {}
    url = r.get("redirect_url")
    return {
        "external_id": r.get("id"),
        "title": r.get("title"),
        "company": comp.get("display_name") if isinstance(comp, dict) else _s(comp),
        "description": r.get("description"),
        "location": loc.get("display_name") if isinstance(loc, dict) else _s(loc),
        "job_type": r.get("contract_time"),
        "application_url": url,
        "source_url": url,
    }


# ---------- web pages: JSON-LD JobPosting ----------
class PageParser(HTMLParser):
    """Collects <script type=application/ld+json> blocks and <a href> links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ld: list[str] = []
        self.links: list[str] = []
        self._in_ld = False
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and (a.get("type") or "").lower().startswith("application/ld+json"):
            self._in_ld, self._buf = True, []
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld.append("".join(self._buf))


def parse_page(page_html: str) -> PageParser:
    p = PageParser()
    p.feed(page_html)
    return p


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "itemListElement", "item"):
            if key in node:
                yield from _walk(node[key])


def extract_jobpostings(ld_blocks: list[str]) -> list[dict]:
    out = []
    for block in ld_blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if "JobPosting" in types:
                out.append(node)
    return out


def jobposting_to_raw(jp: dict, page_url: str) -> dict:
    org = jp.get("hiringOrganization")
    locs = jp.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    places = []
    for l in locs:
        addr = l.get("address") if isinstance(l, dict) else None
        if isinstance(addr, dict):
            parts = [_s(addr.get("addressLocality")), _s(addr.get("addressRegion")), _s(addr.get("addressCountry"))]
            places.append(", ".join(p for p in parts if p))
        elif isinstance(addr, str):
            places.append(addr)
    remote = "TELECOMMUTE" in _s(jp.get("jobLocationType")).upper()

    sal = None
    bs = jp.get("baseSalary")
    if isinstance(bs, dict):
        v = bs.get("value")
        if isinstance(v, dict):
            sal = salary_text(v.get("minValue", v.get("value")), v.get("maxValue"), bs.get("currency"), v.get("unitText"))
        else:
            sal = salary_text(v, None, bs.get("currency"), None)

    ident = jp.get("identifier")
    # Prefer explicit direct application URL (potentialAction target, applyUrl, directApplyUrl) over generic URL
    direct_apply = None
    act = jp.get("potentialAction")
    if isinstance(act, dict):
        tgt = act.get("target")
        if isinstance(tgt, str):
            direct_apply = tgt
        elif isinstance(tgt, dict):
            direct_apply = tgt.get("url") or tgt.get("urlTemplate")
    elif isinstance(act, list):
        for a in act:
            if isinstance(a, dict) and "Apply" in str(a.get("@type", "")):
                tgt = a.get("target")
                direct_apply = tgt if isinstance(tgt, str) else (tgt.get("url") if isinstance(tgt, dict) else None)
                if direct_apply:
                    break

    direct_apply = direct_apply or _s(jp.get("directApplyUrl")) or _s(jp.get("applicationUrl")) or _s(jp.get("applyUrl"))
    url = direct_apply or _s(jp.get("url")) or page_url
    return {
        "external_id": _s(ident.get("value") if isinstance(ident, dict) else ident) or url,
        "title": _s(jp.get("title")),
        "company": _s(org),
        "company_website": org.get("sameAs") or org.get("url") if isinstance(org, dict) else None,
        "description": _s(jp.get("description")),
        "location": ("Remote" if remote and not places else "; ".join(p for p in places if p)) or None,
        "work_type": "remote" if remote else None,
        "job_type": _s(jp.get("employmentType")),
        "stipend": sal,
        "deadline": jp.get("validThrough"),
        "application_url": url,
        "source_url": page_url,
    }


# ---------- sitemaps ----------
def parse_sitemap(xml_text: str) -> tuple[list[str], list[str]]:
    """-> (page urls, child sitemap urls) from a sitemap or sitemap index. DTDs refused."""
    up = xml_text.upper()
    if "<!DOCTYPE" in up or "<!ENTITY" in up:
        raise ValueError("sitemap contains a DTD/entity declaration; refusing to parse")
    root = ET.fromstring(xml_text)
    pages, children = [], []
    for el in root.iter():
        name = el.tag.split("}")[-1]
        if name not in ("url", "sitemap"):
            continue
        loc = next((c.text.strip() for c in el if c.tag.split("}")[-1] == "loc" and c.text), None)
        if loc:
            (pages if name == "url" else children).append(loc)
    return pages, children


# ---------- RSS / Atom ----------
def parse_feed(xml_text: str) -> list[dict]:
    """RSS 2.0 / Atom entries -> raw dicts. DTDs/entities are refused (XML bomb protection)."""
    up = xml_text.upper()
    if "<!DOCTYPE" in up or "<!ENTITY" in up:
        raise ValueError("feed contains a DTD/entity declaration; refusing to parse")
    root = ET.fromstring(xml_text)
    items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    out = []
    for it in items:
        f: dict[str, str] = {}
        for c in it:
            name = c.tag.split("}")[-1]
            if name == "link":
                href = c.get("href") or (c.text or "").strip()
                if href and (name not in f or c.get("rel") == "alternate"):
                    f[name] = href
            elif name not in f:
                f[name] = (c.text or "").strip()
        link = f.get("link")
        out.append({
            "external_id": f.get("guid") or f.get("id") or link,
            "title": f.get("title"),
            "description": f.get("description") or f.get("summary") or f.get("content"),
            "application_url": link,
            "source_url": link,
        })
    return out
