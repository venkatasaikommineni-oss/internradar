"""Shared HTTP layer for every discovery source.

  * one pooled client (connection reuse, gzip) instead of a new TLS handshake per call
  * polite: at most `host_concurrency` simultaneous requests to any one host
  * resilient: retry + exponential backoff on timeouts / 429 / 5xx, honours Retry-After
  * safe: secrets in query strings never reach logs, run records or error messages
"""
import logging
import random
import re
import socket
import threading
import time
from ipaddress import ip_address
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from ...config import settings

log = logging.getLogger("internradar.net")

_SECRET_KEY = re.compile(r"(?i)^(app_key|api_key|apikey|key|token|secret|access_token|auth|password)$")
_SECRET_IN_TEXT = re.compile(r"(?i)\b(app_key|api_key|apikey|access_token|token|secret|password|key)=[^&\s'\"<>)]+")
_RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_BYTES = 15_000_000


class FetchError(RuntimeError):
    """A request failed for good (after retries). Message is safe to store/show."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def redact_url(url: str) -> str:
    try:
        p = urlsplit(str(url))
        q = [(k, "***" if _SECRET_KEY.match(k) else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
        return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q, safe="*"), ""))
    except ValueError:
        return "<url>"


def redact_text(text: str) -> str:
    """Scrub key=value secrets from any message before it is logged or stored."""
    return _SECRET_IN_TEXT.sub(lambda m: f"{m.group(1)}=***", str(text))


# ---------- client / politeness ----------
_lock = threading.Lock()
_client: httpx.Client | None = None
_transport: httpx.BaseTransport | None = None  # tests inject httpx.MockTransport here
_gates: dict[str, threading.BoundedSemaphore] = {}
_sleep = time.sleep  # replaced in tests


def set_transport(transport: httpx.BaseTransport | None) -> None:
    global _client, _transport
    with _lock:
        if _client is not None:
            _client.close()
        _client, _transport = None, transport


def _get_client() -> httpx.Client:
    global _client
    with _lock:
        if _client is None:
            _client = httpx.Client(
                timeout=settings.http_timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": settings.user_agent,
                    "Accept": "application/json, text/html;q=0.9, application/xml;q=0.8, */*;q=0.5",
                },
                limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
                transport=_transport,
            )
        return _client


def _gate(host: str) -> threading.BoundedSemaphore:
    with _lock:
        g = _gates.get(host)
        if g is None:
            g = _gates[host] = threading.BoundedSemaphore(max(1, settings.host_concurrency))
        return g


def _backoff(attempt: int, resp: httpx.Response | None) -> float:
    if resp is not None:
        ra = resp.headers.get("retry-after", "").strip()
        if ra.isdigit():
            return float(min(int(ra), 20))
    return min(2**attempt, 8) * 0.5 + random.random() * 0.4


def request(
    url: str,
    *,
    method: str = "GET",
    params: dict | None = None,
    headers: dict | None = None,
    retries: int | None = None,
) -> httpx.Response:
    """Response for any non-transient status (404 etc. are returned, not raised -
    callers decide what they mean). Transient failures are retried, then raise FetchError."""
    retries = settings.http_retries if retries is None else retries
    host = urlsplit(url).netloc
    last, status, resp = "no attempt", None, None
    for attempt in range(retries + 1):
        resp = None
        try:
            with _gate(host):
                resp = _get_client().request(method, url, params=params, headers=headers)
        except httpx.HTTPError as e:
            last, status = type(e).__name__, None
        else:
            if resp.status_code not in _RETRY_STATUS:
                if len(resp.content) > MAX_BYTES:
                    raise FetchError(f"{redact_url(url)}: response larger than {MAX_BYTES // 1_000_000} MB")
                return resp
            last, status = f"HTTP {resp.status_code}", resp.status_code
        if attempt < retries:
            _sleep(_backoff(attempt, resp))
    raise FetchError(f"{redact_url(url)}: {last} after {retries + 1} attempt(s)", status)


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> Any:
    r = request(url, params=params, headers=headers)
    if r.status_code >= 400:
        raise FetchError(f"{redact_url(url)}: HTTP {r.status_code}", r.status_code)
    try:
        return r.json()
    except ValueError:
        raise FetchError(f"{redact_url(url)}: response is not valid JSON", r.status_code) from None


def get_text(url: str, params: dict | None = None, headers: dict | None = None) -> str:
    r = request(url, params=params, headers=headers)
    if r.status_code >= 400:
        raise FetchError(f"{redact_url(url)}: HTTP {r.status_code}", r.status_code)
    return r.text


# ---------- SSRF guard for crawled hosts ----------
_public_cache: dict[str, bool] = {}


def is_public_host(host: str) -> bool:
    """True only if every address the name resolves to is a public one."""
    host = host.strip("[]").lower()
    if host in _public_cache:
        return _public_cache[host]
    try:
        try:
            ips = [ip_address(host)]
        except ValueError:
            ips = [ip_address(ai[4][0]) for ai in socket.getaddrinfo(host, None)]
        ok = bool(ips) and all(ip.is_global for ip in ips)
    except (OSError, ValueError):
        ok = False
    _public_cache[host] = ok
    return ok
