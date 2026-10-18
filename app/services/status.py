"""Listing status maintenance.

Statuses: open | closing_soon | expired | unverified
status_basis says WHY a listing has its status, because evidence differs in strength:

  source_sync  the company's own board stopped listing it   -> closed (strongest; only a re-listing reopens it)
  source_live  the company's own board listed it at the last sync and it has no deadline
               -> open (confirmed available; expires after LIVE_TTL_HOURS without a fresh sync)
  link_check   the application page is gone (404/410) or says the role is closed
  deadline     derived from the stated deadline (a passed deadline is not proof the role is gone,
               which is why the stronger bases above take precedence)
  none         nothing confirms it -> "unverified" (never assumed open)"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from sqlalchemy import and_, not_, or_, select, update
from sqlalchemy.orm import Session

from ..ai.status import compute_status as _compute_status
from ..config import settings
from ..models import Internship, utcnow
from . import pagecheck
from .sources import net


def compute_status(
    deadline: datetime | None, link_ok: bool | None, now: datetime | None = None, live: bool = False
) -> tuple[str, str]:
    """`live` = the record was just seen on a source that publishes its complete list of open roles."""
    return _compute_status(
        deadline, link_ok=link_ok, now=now or utcnow(), closing_soon_days=settings.closing_soon_days, live=live
    )


def refresh_statuses(db: Session) -> dict[str, int]:
    """Bulk SQL recompute (cheap enough to run every few minutes)."""
    now = utcnow()
    soon = now + timedelta(days=settings.closing_soon_days)
    I = Internship
    changeable = I.status_basis != "source_sync"  # closed by the source: only a re-listing reopens it
    link_alive = or_(I.link_ok.is_(None), I.link_ok.is_(True))
    live_fresh = and_(I.status_basis == "source_live", I.last_seen_at >= now - timedelta(hours=settings.live_ttl_hours))

    def run(values, *conds):
        return db.execute(update(I).where(*conds).values(**values)).rowcount or 0

    counts = {
        "expired_link": run({"status": "expired", "status_basis": "link_check"}, changeable, I.link_ok.is_(False)),
        "expired_deadline": run({"status": "expired", "status_basis": "deadline"}, changeable, link_alive, I.deadline.is_not(None), I.deadline < now),
        "closing_soon": run({"status": "closing_soon", "status_basis": "deadline"}, changeable, link_alive, I.deadline >= now, I.deadline < soon),
        "open": run({"status": "open", "status_basis": "deadline"}, changeable, link_alive, I.deadline >= soon),
        # no deadline: stays open only while the company board's confirmation is fresh
        "unverified": run({"status": "unverified", "status_basis": "none"}, changeable, link_alive, I.deadline.is_(None), not_(live_fresh)),
    }
    db.commit()
    return counts


# ---------- broken / closed link detection ----------
def _probe(url: str) -> bool | None:
    """True = reachable and not marked closed, False = confirmed gone (404/410) or the page
    says the role is closed, None = inconclusive (timeouts, 403/429 bot-blocking, 5xx...) -
    never marks a listing dead on doubt."""
    try:
        r = net.request(url, retries=0)  # GET: the page text is needed to spot "no longer accepting" notices
    except net.FetchError:
        return None
    if r.status_code in (404, 410):
        return False
    if 200 <= r.status_code < 400:
        if settings.detect_closed_pages and "html" in r.headers.get("content-type", "").lower():
            if pagecheck.classify_page(r.text[:400_000]) is False:
                return False
        return True
    return None


def check_links(db: Session, limit: int | None = None) -> dict[str, int]:
    limit = limit or settings.link_check_batch
    cutoff = utcnow() - timedelta(hours=settings.link_recheck_hours)
    I = Internship
    rows = db.execute(
        select(I.id, I.application_url)
        .where(
            I.status != "expired",
            I.status_basis.not_in(("source_live", "source_sync")),  # the company board already confirms those
            or_(I.last_checked_at.is_(None), I.last_checked_at < cutoff),
        )
        .order_by(I.last_checked_at.asc().nulls_first())
        .limit(limit)
    ).all()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda r: _probe(r.application_url), rows))
    now = utcnow()
    tally = {"checked": len(rows), "ok": 0, "broken": 0, "inconclusive": 0}
    for row, res in zip(rows, results):
        vals = {"last_checked_at": now}
        if res is not None:  # keep previous link_ok when inconclusive
            vals["link_ok"] = res
        db.execute(update(I).where(I.id == row.id).values(**vals))
        tally["ok" if res else "broken" if res is False else "inconclusive"] += 1
    db.commit()
    refresh_statuses(db)
    return tally
