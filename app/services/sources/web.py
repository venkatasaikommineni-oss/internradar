"""Web sources for sites that publish structured data but have no API.

Only for sites you are permitted to read. Safeguards built in:
  * only the pages/sitemaps/hosts YOU list in the config are fetched (no open crawling)
  * robots.txt is honoured; if it cannot be read, the host is treated as disallowed
  * per-host delay (and the site's Crawl-delay if larger), page cap, size cap
  * hosts that resolve to private/local addresses are refused (SSRF); redirects must stay on the host
  * data is read from schema.org JobPosting JSON-LD (what career pages publish for
    search engines), not scraped from page layout
"""
import logging
import re
import time
from typing import Iterable
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree.ElementTree import ParseError

from ...config import settings
from ..normalize import canonical_url
from . import net
from .base import looks_like_internship
from .mappers import extract_jobpostings, jobposting_to_raw, parse_feed, parse_page, parse_sitemap

log = logging.getLogger("internradar.web")
ROBOTS_TOKEN = "InternRadar"
MAX_BYTES = 2_000_000
MAX_SITEMAPS = 10


class PoliteFetcher:
    def __init__(self):
        self._robots: dict[str, RobotFileParser] = {}
        self._last: dict[str, float] = {}

    def close(self):  # the pooled client is shared and lives in net.py
        pass

    def _load_robots(self, origin: str) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            r = net.request(origin + "/robots.txt", retries=1)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            elif r.status_code in (404, 410):
                rp.parse([])  # no robots.txt = no restrictions
            else:  # 401/403/...: cannot confirm permission -> do not fetch
                rp.parse(["User-agent: *", "Disallow: /"])
        except net.FetchError:  # unreachable / 5xx: cannot confirm permission
            rp.parse(["User-agent: *", "Disallow: /"])
        return rp

    def get(self, url: str, accept_xml: bool = False) -> str | None:
        """Page text, or None if refused/unavailable (always logged)."""
        if not canonical_url(url):
            log.warning("refusing non-public or invalid URL: %s", url)
            return None
        p = urlsplit(url)
        if not net.is_public_host(p.hostname or ""):
            log.warning("refusing host that does not resolve to a public address: %s", p.hostname)
            return None
        origin = f"{p.scheme}://{p.netloc}"
        rp = self._robots.get(origin) or self._robots.setdefault(origin, self._load_robots(origin))
        if not rp.can_fetch(ROBOTS_TOKEN, url):
            log.warning("robots.txt disallows %s", url)
            return None
        wait = max(settings.crawl_delay_seconds, float(rp.crawl_delay(ROBOTS_TOKEN) or 0))
        gap = time.monotonic() - self._last.get(origin, 0.0)
        if gap < wait:
            time.sleep(wait - gap)
        try:
            r = net.request(url, retries=1)
        except net.FetchError as e:
            log.warning("fetch failed: %s", e)
            return None
        finally:
            self._last[origin] = time.monotonic()
        if r.status_code != 200 or len(r.content) > MAX_BYTES:
            log.warning("skipping %s (status %s, %s bytes)", url, r.status_code, len(r.content))
            return None
        if urlsplit(str(r.url)).netloc != p.netloc:
            log.warning("redirect left the host: %s -> %s", url, r.url)
            return None
        ctype = r.headers.get("content-type", "").lower()
        if not accept_xml and "html" not in ctype:
            return None
        return r.text


class JobPostingPagesSource:
    """Config: {"type":"jobposting_pages","name":"acme","company":"Acme",
                "pages":["https://acme.com/careers"],          # listing and/or detail pages
                "link_pattern":"/careers/intern",               # follow matching same-host links
                "sitemaps":["https://acme.com/sitemap.xml"],    # discover detail pages from sitemaps
                "url_pattern":"intern",                          # which sitemap URLs to read (default: 'intern')
                "max_pages":40}"""

    kind = "jobposting_pages"
    complete_listing = False

    def __init__(self, cfg: dict):
        self.name = str(cfg["name"])[:60]
        self.pages: list[str] = list(cfg.get("pages") or [])
        self.sitemaps: list[str] = list(cfg.get("sitemaps") or [])
        self.link_pattern = re.compile(cfg["link_pattern"]) if cfg.get("link_pattern") else None
        self.url_pattern = re.compile(cfg.get("url_pattern") or "intern", re.I)
        self.max_pages = min(int(cfg.get("max_pages", settings.crawl_max_pages)), settings.crawl_max_pages)
        self.company = cfg.get("company")

    def _postings(self, page_html: str, url: str) -> Iterable[dict]:
        for jp in extract_jobpostings(parse_page(page_html).ld):
            raw = jobposting_to_raw(jp, url)
            if self.company and not raw.get("company"):
                raw["company"] = self.company
            yield raw

    def _sitemap_urls(self, fetcher: PoliteFetcher) -> tuple[list[str], int]:
        """-> (candidate page URLs, number of sitemaps successfully read)."""
        out, ok, seen, todo = [], 0, set(), list(self.sitemaps)
        while todo and len(seen) < MAX_SITEMAPS:
            sm = todo.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            text = fetcher.get(sm, accept_xml=True)
            if text is None:
                continue
            try:
                pages, children = parse_sitemap(text)
            except (ValueError, ParseError) as e:
                log.warning("%s: unreadable sitemap %s (%s)", self.name, sm, e)
                continue
            ok += 1
            host = urlsplit(sm).netloc
            todo.extend(c for c in children if urlsplit(c).netloc == host)
            out.extend(u for u in pages if urlsplit(u).netloc == host and self.url_pattern.search(u))
        return out, ok

    def fetch(self) -> Iterable[dict]:
        fetcher = PoliteFetcher()
        ok, queue, seen = 0, [], set(self.pages)
        for url in self.pages:
            page = fetcher.get(url)
            if page is None:
                continue
            ok += 1
            yield from self._postings(page, url)
            if self.link_pattern:
                host = urlsplit(url).netloc
                for href in parse_page(page).links:
                    absu = urljoin(url, href).split("#")[0]
                    if urlsplit(absu).netloc == host and self.link_pattern.search(absu) and absu not in seen:
                        seen.add(absu)
                        queue.append(absu)
        if self.sitemaps:
            urls, sm_ok = self._sitemap_urls(fetcher)
            ok += sm_ok
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    queue.append(u)
        for url in queue[: self.max_pages]:
            page = fetcher.get(url)
            if page is not None:
                ok += 1
                yield from self._postings(page, url)
        if ok == 0:  # nothing readable (blocked / down): report failure, not an empty success
            raise RuntimeError(f"{self.name}: no page could be fetched (robots.txt, network or URL problem)")


class RSSSource:
    """Config: {"type":"rss","name":"acme_feed","url":"https://.../jobs.xml","company":"Acme"}"""

    kind = "rss"

    def __init__(self, cfg: dict):
        self.name = str(cfg["name"])[:60]
        self.url = cfg["url"]
        self.company = cfg.get("company") or self.name
        self.complete_listing = bool(cfg.get("complete_listing", False))

    def fetch(self) -> Iterable[dict]:
        text = PoliteFetcher().get(self.url, accept_xml=True)
        if text is None:
            raise RuntimeError(f"{self.name}: feed could not be fetched")
        for raw in parse_feed(text):
            if looks_like_internship(raw):
                yield {**raw, "company": self.company}
