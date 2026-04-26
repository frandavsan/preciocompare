"""
In-process job scheduler — runs refresh and canary jobs on the same
event loop as the FastAPI/uvicorn worker.

Requires a single-worker deployment (``--workers 1``) to avoid
duplicate job execution and SQLite contention.

Jobs:
  - **refresh**: re-fetches all cached queries (daily 08:00 UTC by default).
  - **canary**: health-check probes against every store (every 4 h by default).

All schedules are configurable via environment variables
(``REFRESH_CRON``, ``CANARY_INTERVAL_HOURS``, ``SCHEDULER_ENABLED``).
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .fetching import cache as _cache

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _refresh_job() -> None:
    """Runs a full cache refresh followed by canary checks."""
    from .refresh import refresh_all
    from .monitoring.canary import run_all as run_canaries
    from .monitoring.alerts import alert_canary_failures

    logger.info("Scheduled refresh starting")
    try:
        counts = await refresh_all()
        total = sum(counts.values())
        logger.info("Refresh complete: %d products across %d stores", total, len(counts))
    except Exception:
        logger.exception("Scheduled refresh failed")
        return

    try:
        failures = await run_canaries()
        if failures:
            logger.warning("Canary: %d failure(s)", len(failures))
            await alert_canary_failures(failures)
        else:
            logger.info("Canary: all checks passed")
    except Exception:
        logger.exception("Post-refresh canary failed")


async def _canary_job() -> None:
    """Runs canary health checks (standalone, between refreshes)."""
    from .monitoring.canary import run_all as run_canaries
    from .monitoring.alerts import alert_canary_failures

    logger.info("Scheduled canary starting")
    try:
        failures = await run_canaries()
        if failures:
            logger.warning("Canary: %d failure(s)", len(failures))
            await alert_canary_failures(failures)
        else:
            logger.info("Canary: all checks passed")
    except Exception:
        logger.exception("Scheduled canary failed")


def start() -> None:
    """Creates and starts the scheduler if enabled via settings."""
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return

    _scheduler = AsyncIOScheduler(timezone="UTC")

    if not _cache.CACHE_DISABLED:
        _scheduler.add_job(
            _refresh_job,
            trigger=CronTrigger.from_crontab(settings.refresh_cron),
            id="refresh",
            name="Cache refresh + canary",
            misfire_grace_time=3600,
        )
    else:
        logger.info("Refresh job skipped (cache.CACHE_DISABLED=True)")

    _scheduler.add_job(
        _canary_job,
        trigger=IntervalTrigger(hours=settings.canary_interval_hours),
        id="canary",
        name="Canary health checks",
        misfire_grace_time=900,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — refresh=%s, canary=every %dh",
        "disabled" if _cache.CACHE_DISABLED else settings.refresh_cron,
        settings.canary_interval_hours,
    )


def stop() -> None:
    """Shuts down the scheduler if running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def get_status() -> dict:
    """Returns scheduler state for the /health endpoint."""
    if _scheduler is None:
        return {"enabled": False}

    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_utc": next_run.isoformat() if next_run else None,
        })

    return {
        "enabled": True,
        "running": _scheduler.running,
        "jobs": jobs,
    }
