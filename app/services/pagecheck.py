"""Is a job page still accepting applications? Pure functions (no network, no DB).

Many career sites keep an expired posting online (HTTP 200) with a banner such as
"This position has been filled". A plain link check calls those listings alive;
reading the page catches them. Deliberately conservative: only structured data that
says the posting expired, or an unambiguous closed notice near the top of the page."""
import re
from datetime import datetime, timezone

from .normalize import parse_deadline
from .sources.mappers import extract_jobpostings, parse_page

_CLOSED = re.compile(
    r"no longer (?:accepting|available|open|active)"
    r"|(?:position|role|job|posting|listing|opening|vacancy|internship)(?: has| is| was)?(?: now)?(?: been)? (?:filled|closed|expired|removed)"
    r"|applications?(?: are| is| have been| has been)?(?: now)? closed"
    r"|this (?:job|position|role|internship|posting)(?: is)? (?:no longer|has expired|has been filled|has been closed)"
    r"|sorry,? (?:this|the) (?:job|position|role|internship)"
    r"|job (?:not found|no longer exists)",
    re.I,
)
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_NOISE = re.compile(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>")
_TAGS = re.compile(r"<[^>]+>")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def classify_page(page_html: str, now: datetime | None = None) -> bool | None:
    """False = the page says this posting is closed/expired; None = no evidence of closure."""
    now = now or _utcnow()
    postings = extract_jobpostings(parse_page(page_html).ld)
    if postings:  # structured data wins over page boilerplate
        for jp in postings:
            valid_through = parse_deadline(jp.get("validThrough"))
            if valid_through is not None and valid_through < now:
                return False
        return None
    title = _TITLE.search(page_html)
    visible = _TAGS.sub(" ", _NOISE.sub(" ", page_html))
    head = f"{title.group(1) if title else ''} {visible[:6000]}"
    return False if _CLOSED.search(head) else None
