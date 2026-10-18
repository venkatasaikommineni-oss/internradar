"""Source adapters. Each exposes `.name`, `.kind` and `.fetch()` yielding raw dicts with
the standard keys (title, company, description, location, application_url, ...), and a
`.complete_listing` flag: True only when the source publishes its COMPLETE list of open
roles, so that a listing which later disappears can be treated as closed.
Only use APIs/feeds whose terms permit this use - adapters never scrape HTML."""
from typing import Any, Iterable

from ..normalize import INTERN_RE
from . import net
from .net import get_json as http_get_json  # noqa: F401  (kept: imported by older code/tests)


def looks_like_internship(raw: dict) -> bool:
    """Cheap pre-filter for sources that return a company's *entire* job board,
    so import stats count internship candidates, not every engineering role."""
    return bool(INTERN_RE.search(str(raw.get("title") or "")) or INTERN_RE.search(str(raw.get("job_type") or "")))


def dig(obj: Any, path: str | None) -> Any:
    """Dotted-path lookup: dig(item, 'company.name')."""
    if not path:
        return None
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


class ListSource:
    """In-memory records (tests, one-off imports from your own curated file)."""

    kind = "list"
    complete_listing = False

    def __init__(self, name: str, records: list[dict]):
        self.name, self._records = name, records

    def fetch(self) -> Iterable[dict]:
        return iter(self._records)


class JSONFeedSource:
    """Generic adapter for any authorized JSON API; configured via sources.json / FEED_SOURCES."""

    kind = "json_feed"

    def __init__(self, cfg: dict):
        self.name = str(cfg["name"])[:60]
        self.url = cfg["url"]
        self.params = cfg.get("params")
        self.headers = cfg.get("headers")
        self.items_path = cfg.get("items_path")
        self.field_map = cfg["field_map"]
        # set true only if the feed returns EVERY open listing: anything that later
        # disappears from it is then marked closed (status_basis = source_sync)
        self.complete_listing = bool(cfg.get("complete_listing", False))

    def fetch(self) -> Iterable[dict]:
        data = net.get_json(self.url, self.params, self.headers)
        items = dig(data, self.items_path) if self.items_path else data
        if not isinstance(items, list):
            raise ValueError(f"{self.name}: items_path '{self.items_path}' did not resolve to a list")
        for item in items:
            yield {field: dig(item, path) for field, path in self.field_map.items()}


class RemotiveSource:
    """Remotive public API (remote roles). Check their terms: attribution required
    and requests must be infrequent - the default 12h schedule respects that."""

    kind = "remotive"
    name = "remotive"
    complete_listing = False  # search subset, not the full catalogue
    URL = "https://remotive.com/api/remote-jobs"
    OK_REGIONS = ("india", "worldwide", "anywhere", "asia")

    def fetch(self) -> Iterable[dict]:
        data = net.get_json(self.URL, params={"search": "intern"})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            raise ValueError("remotive: unexpected response shape")
        for j in jobs:
            region = (j.get("candidate_required_location") or "").lower()
            if region and not any(r in region for r in self.OK_REGIONS):
                continue
            yield {
                "external_id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company_name"),
                "description": j.get("description"),
                "location": f"Remote ({j.get('candidate_required_location') or 'Worldwide'})",
                "job_type": j.get("job_type"),
                "work_type": "remote",
                "stipend": j.get("salary"),
                "skills": j.get("tags"),
                "application_url": j.get("url"),
                "source_url": j.get("url"),
            }
