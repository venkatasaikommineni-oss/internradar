"""Public job-board APIs offered by applicant-tracking systems for exactly this
purpose (embedding/aggregating a company's own listings). One source per board,
so a board that disappears or is mistyped fails alone and is reported.

These return the company's COMPLETE list of open roles, so a listing that later
vanishes from the board is genuinely closed -> complete_listing = True."""
import logging
from typing import Iterable

from ...config import settings
from . import net
from .base import looks_like_internship
from .mappers import ashby_to_raw, greenhouse_to_raw, lever_to_raw

log = logging.getLogger("internradar.ats")


def _label(token: str) -> str:
    return token.replace("-", " ").replace("_", " ").title()


class GreenhouseSource:
    """Two-phase fetch. A board can hold hundreds of roles, and `?content=true` ships
    every description (megabytes). So: list the board without content (tiny), keep the
    internships, and fetch the full description for those only."""

    kind = "greenhouse"
    complete_listing = True

    def __init__(self, token: str, company: str | None = None, details: bool = True):
        self.token, self.company, self.details = token, company, details
        self.name = f"greenhouse:{token}"[:60]

    def fetch(self) -> Iterable[dict]:
        base = f"https://boards-api.greenhouse.io/v1/boards/{self.token}"
        company = self.company
        if not company:
            try:
                company = net.get_json(base).get("name")
            except Exception:  # cosmetic; the jobs call below reports real failures
                company = None
        company = company or _label(self.token)

        data = net.get_json(f"{base}/jobs", params=None if self.details else {"content": "true"})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise ValueError(f"{self.name}: unexpected response shape")

        interns = [j for j in jobs if looks_like_internship(greenhouse_to_raw(j))]
        for i, j in enumerate(interns):
            raw = greenhouse_to_raw(j)
            if self.details and i < settings.greenhouse_detail_cap:
                try:
                    raw = {**raw, **{k: v for k, v in greenhouse_to_raw(net.get_json(f"{base}/jobs/{j['id']}")).items() if v}}
                except Exception as e:  # keep the listing (it IS on the board) without its description
                    log.warning("%s: details for job %s unavailable (%s)", self.name, j.get("id"), net.redact_text(str(e)))
            yield {**raw, "company": company}


class LeverSource:
    kind = "lever"
    complete_listing = True
    PAGE = 100

    def __init__(self, company_token: str, company: str | None = None, region: str | None = None):
        self.token, self.company = company_token, company
        self.host = "api.eu.lever.co" if (region or "").lower() == "eu" else "api.lever.co"
        self.name = f"lever:{company_token}"[:60]

    def fetch(self) -> Iterable[dict]:
        company = self.company or _label(self.token)
        url = f"https://{self.host}/v0/postings/{self.token}"
        skip, seen_first = 0, set()
        for _ in range(50):  # hard cap: 5,000 postings
            page = net.get_json(url, params={"mode": "json", "skip": skip, "limit": self.PAGE})
            if not isinstance(page, list):
                raise ValueError(f"{self.name}: unexpected response shape")
            first = page[0].get("id") if page else None
            if first is not None and first in seen_first:
                break  # the server ignored paging and returned the same page again
            seen_first.add(first)
            for p in page:
                raw = lever_to_raw(p)
                if looks_like_internship(raw):
                    yield {**raw, "company": company}
            if len(page) < self.PAGE:
                break
            skip += self.PAGE


class AshbySource:
    kind = "ashby"
    complete_listing = True

    def __init__(self, board: str, company: str | None = None):
        self.board, self.company = board, company
        self.name = f"ashby:{board}"[:60]

    def fetch(self) -> Iterable[dict]:
        data = net.get_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{self.board}",
            params={"includeCompensation": "true"},
        )
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise ValueError(f"{self.name}: unexpected response shape")
        company = self.company or _label(self.board)
        for j in jobs:
            if j.get("isListed") is False:
                continue
            raw = ashby_to_raw(j)
            if looks_like_internship(raw):
                yield {**raw, "company": company}
