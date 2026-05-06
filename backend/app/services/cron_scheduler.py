"""APScheduler wiring for the daily refresh cron jobs.

Kept separate from the runner modules so the executors stay focused on
per-run logic. This module knows how to register the daily jobs, sync
the schedule from `AppSettings`, start the background scheduler thread
on FastAPI startup, and tear it down on shutdown.

Two independent jobs are registered:

* ``daily_refresh`` – market-data pipeline (existing behaviour).
* ``daily_jobs_scrape`` – career-portal scrape pipeline. Uses its own
  cron expression and lock so it can run side-by-side with the market
  refresh.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models.settings import AppSettings
from app.services.jobs_service import run_jobs_blocking
from app.services.refresh_runner import run_refresh_all_blocking

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _job() -> None:
    run_refresh_all_blocking()


def _jobs_job() -> None:
    run_jobs_blocking()


def _schedule(hour: int, minute: int) -> None:
    scheduler.add_job(
        _job,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_refresh",
        replace_existing=True,
    )


def _schedule_jobs(hour: int, minute: int) -> None:
    scheduler.add_job(
        _jobs_job,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_jobs_scrape",
        replace_existing=True,
    )


def sync_scheduler_from_db() -> None:
    """Re-read both cron expressions from `AppSettings` and replace the jobs."""
    db = SessionLocal()
    try:
        row = db.get(AppSettings, 1) or AppSettings(id=1)
        db.add(row)
        db.commit()
        _schedule(row.update_hour, row.update_minute)
        _schedule_jobs(row.jobs_update_hour, row.jobs_update_minute)
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the APScheduler thread (idempotent)."""
    if scheduler.running:
        sync_scheduler_from_db()
        return
    sync_scheduler_from_db()
    scheduler.start()


def shutdown_scheduler(*, wait: bool = False) -> None:
    """Stop the APScheduler thread on application shutdown.

    `wait=False` is the default so a slow in-flight job cannot block the
    FastAPI lifespan from completing — we simply detach and rely on the
    daemon thread being terminated with the process.
    """
    if not scheduler.running:
        return
    try:
        scheduler.shutdown(wait=wait)
    except Exception:  # pragma: no cover - defensive, shutdown is best-effort
        logger.exception("Failed to shut down APScheduler cleanly")
