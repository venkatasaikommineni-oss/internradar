"""Pure listing-status logic, with no database or backend dependencies."""
from datetime import datetime, timedelta, timezone

def compute_status(deadline, link_ok=None, now=None, closing_soon_days=7, live=False):
    """`live` = seen on a source that publishes its complete list of open roles (no deadline needed)."""
    now = now or datetime.now(timezone.utc)
    if link_ok is False:
        return "expired", "link_check"
    if deadline is None:
        return ("open", "source_live") if live else ("unverified", "none")
    # Normalize naive datetimes to UTC to avoid mixed datetime comparisons.
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if deadline < now:
        return "expired", "deadline"
    if deadline < now + timedelta(days=closing_soon_days):
        return "closing_soon", "deadline"
    return "open", "deadline"
