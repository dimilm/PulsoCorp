"""APScheduler wiring for the daily refresh cron job.

Kept separate from `refresh_runner.py` so the executor module stays
focused on per-run logic. This module only knows how to register the
daily job, sync the schedule from `AppSettings`, start the background
scheduler thread on FastAPI startup, and tear it down on shutdown.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models.settings import AppSettings
from app.services.refresh_runner import run_refresh_all_blocking

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _job() -> None:
    run_refresh_all_blocking()


def _schedule(hour: int, minute: int) -> None:
    scheduler.add_job(
        _job,
        "cron",
        hour=hour,
        minute=minute,
        id="daily_refresh",
        replace_existing=True,
    )


def sync_scheduler_from_db() -> None:
    """Re-read the cron expression from `AppSettings` and replace the job."""
    db = SessionLocal()
    try:
        row = db.get(AppSettings, 1) or AppSettings(id=1)
        db.add(row)
        db.commit()
        _schedule(row.update_hour, row.update_minute)
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
