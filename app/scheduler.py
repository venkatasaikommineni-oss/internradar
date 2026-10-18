"""Background jobs (in-process). For multi-worker deployments run the scheduler
in exactly one process (or move these jobs to a dedicated worker)."""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from .config import settings
from .database import SessionLocal
from .models import ImportRun, utcnow
from .services.importer import run_all_sources, run_many
from .services.sources import get_sources
from .services.status import check_links, refresh_statuses

log = logging.getLogger("internradar.scheduler")


def _with_session(fn):
    def wrapper():
        db = SessionLocal()
        try:
            fn(db)
        except Exception:
            log.exception("scheduled job %s failed", fn.__name__)
        finally:
            db.close()

    wrapper.__name__ = fn.__name__
    return wrapper


def startup_import(db) -> None:
    """Run discovery pipeline on boot so freshly discovered internships
    and updated sources are always available."""
    sources = get_sources()
    if not sources:
        return
    log.info("Running discovery pipeline for %d active source(s)...", len(sources))
    run_many(db, sources)


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="UTC")
    opts = dict(max_instances=1, coalesce=True)
    sched.add_job(_with_session(run_all_sources), "interval", hours=settings.import_interval_hours, jitter=120, **opts)
    sched.add_job(_with_session(refresh_statuses), "interval", minutes=settings.status_refresh_minutes, **opts)
    sched.add_job(_with_session(check_links), "interval", hours=settings.link_check_interval_hours, **opts)
    if settings.import_on_start:
        sched.add_job(
            _with_session(startup_import), "date", run_date=datetime.now(timezone.utc) + timedelta(seconds=5), **opts
        )
    sched.start()
    return sched
