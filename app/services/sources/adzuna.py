"""Adzuna job-search API (licensed aggregator; free API keys). It is the broad-recall
source: it indexes many portals under its own agreements, which is the legitimate
route to listings that those portals do not let us scrape. Terms require showing
"Jobs by Adzuna" attribution and linking through `redirect_url` (our application_url)."""
from typing import Iterable

from ...config import settings
from . import net
from .base import looks_like_internship
from .mappers import adzuna_to_raw

DEFAULT_QUERIES = [
    "internship", "software intern", "web developer intern", "data science intern",
    "machine learning intern", "cyber security intern", "cloud devops intern",
    "business analyst intern", "ui ux design intern", "digital marketing intern",
]


class AdzunaSource:
    kind = "adzuna"
    complete_listing = False  # search results, not the full catalogue
    PER_PAGE = 50

    def __init__(self, cfg: dict | None = None):
        cfg = cfg or {}
        self.name = str(cfg.get("name", "adzuna"))[:60]
        self.app_id = cfg.get("app_id") or settings.adzuna_app_id
        self.app_key = cfg.get("app_key") or settings.adzuna_app_key
        self.country = str(cfg.get("country") or settings.adzuna_country).lower()
        self.queries = cfg.get("queries") or DEFAULT_QUERIES
        self.pages = max(1, int(cfg.get("pages", 2)))

    def fetch(self) -> Iterable[dict]:
        if not (self.app_id and self.app_key):
            raise ValueError("adzuna: set ADZUNA_APP_ID and ADZUNA_APP_KEY (free keys at developer.adzuna.com)")
        seen: set = set()
        ok, last_err = 0, None
        for q in self.queries:
            for page in range(1, self.pages + 1):
                try:
                    data = net.get_json(
                        f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/{page}",
                        params={
                            "app_id": self.app_id, "app_key": self.app_key, "what": q,
                            "results_per_page": self.PER_PAGE, "sort_by": "date",
                        },
                    )
                except net.FetchError as e:  # one bad query/page must not lose the others
                    last_err = e
                    break
                results = data.get("results") if isinstance(data, dict) else None
                if not isinstance(results, list):
                    last_err = ValueError("adzuna: unexpected response shape")
                    break
                ok += 1
                for r in results:
                    if r.get("id") in seen:
                        continue
                    seen.add(r.get("id"))
                    raw = adzuna_to_raw(r)
                    if looks_like_internship(raw):
                        yield raw
                if len(results) < self.PER_PAGE:
                    break
        if ok == 0 and last_err is not None:
            raise last_err  # every request failed: report it, do not pretend the source is empty
