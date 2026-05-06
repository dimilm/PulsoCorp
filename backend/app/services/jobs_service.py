"""Career-portal scrape pipeline.

Mirrors the architecture of `refresh_runner.py` for the market-data refresh:

* `start_refresh_jobs_background`  – queue a bulk scrape; returns immediately.
* `start_single_jobs_refresh_background` – scrape a single source (admin/test).
* `cancel_current_jobs_refresh`    – flag the active jobs run for cancellation.
* `run_jobs_blocking`              – cron-friendly variant that polls the
  `RunLog` until completion.

The pipeline writes to the same `RunLog` table as the market refresh but
uses `run_type='jobs'`, a separate `RunJobStatus` row per source, and a
dedicated lock name so a market refresh can run in parallel.
"""
from __future__ import annotations

import logging
import time
from datetime import date as date_type
from typing import Callable

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.job_source import JobSnapshot, JobSource, RunJobStatus
from app.models.run_log import RunLog
from app.providers.jobs import (
    ADAPTER_REGISTRY,
    PLAYWRIGHT_ADAPTER_NAMES,
    AdapterError,
    BaseJobAdapter,
)
from app.services import lock_manager, run_pipeline
from app.services.refresh_lock import process_owner
from app.services.refresh_worker import worker as refresh_worker
from app.services.run_status_service import humanize_error

logger = logging.getLogger(__name__)

# Separate lock so a market-data refresh and a job scrape can run side by
# side. The single-source path reuses the same name so two concurrent jobs
# scrapes (cron + manual) cannot overlap each other.
_JOBS_LOCK_NAME = "daily_jobs_refresh"


# ---------------------------------------------------------------------------
# Cancellation registry — thin aliases onto the unified run_pipeline registry.
# Tests that access ``jobs_service._jobs_cancel_lock`` and
# ``jobs_service._cancelled_jobs_run_ids`` continue to work because these
# names point to the *same* objects as ``run_pipeline._cancel_lock`` /
# ``run_pipeline._cancelled_run_ids``.  Run IDs are globally unique (DB
# auto-increment) so sharing the registry with the refresh pipeline never
# causes cross-contamination.
# ---------------------------------------------------------------------------

_jobs_cancel_lock = run_pipeline._cancel_lock
_cancelled_jobs_run_ids = run_pipeline._cancelled_run_ids

# Alias — tests call ``jobs_service.JobsRefreshCancelled``
JobsRefreshCancelled = run_pipeline.RunCancelled


def request_cancel_for_jobs_run(run_id: int) -> None:
    run_pipeline.request_cancel_for_run(run_id)


def is_jobs_cancel_requested(run_id: int) -> bool:
    return run_pipeline.is_cancel_requested(run_id)


def clear_jobs_cancel(run_id: int) -> None:
    run_pipeline.clear_cancel(run_id)


# ---------------------------------------------------------------------------
# Stale-lock recovery (jobs-specific)
# ---------------------------------------------------------------------------

def recover_stale_jobs_locks() -> None:
    """Release the jobs lock if its owner crashed and finalise orphaned runs.

    Called from the FastAPI lifespan alongside ``refresh_lock.recover_stale_locks``.
    Restricts ``RunLog`` finalisation to rows with ``run_type='jobs'`` so that
    a stale jobs lock never accidentally marks market-data runs as errored.
    """
    lock_manager.recover_stale_locks(_JOBS_LOCK_NAME, run_type="jobs")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def start_refresh_jobs_background(*, manual: bool = False) -> dict:
    """Prepare a jobs run synchronously and hand it to the worker thread.

    Returns ``{"run_id", "phase", "status"}`` so the UI can navigate to the
    run view immediately and start polling. ``manual=False`` honours the
    `jobs_enabled` toggle in `AppSettings`; manual triggers always proceed.
    """
    db = SessionLocal()
    try:
        app_settings = run_pipeline.get_or_create_app_settings(db)

        if not manual and not app_settings.jobs_enabled:
            run = RunLog(
                run_type="jobs",
                phase="finished",
                status="skipped",
                started_at=utcnow(),
                finished_at=utcnow(),
                error_details="Job scrape disabled in settings",
            )
            db.add(run)
            db.commit()
            return {"run_id": run.id, "phase": "finished", "status": "skipped"}

        owner = process_owner()
        if not lock_manager.try_acquire_lock(db, _JOBS_LOCK_NAME, owner):
            current = (
                db.query(RunLog)
                .filter(
                    RunLog.run_type == "jobs",
                    RunLog.phase.in_(("queued", "running")),
                )
                .order_by(RunLog.id.desc())
                .first()
            )
            return {
                "run_id": current.id if current else None,
                "phase": "running",
                "status": "already_running",
            }

        run = RunLog(run_type="jobs", phase="queued", started_at=utcnow())
        db.add(run)
        db.commit()

        sources = db.query(JobSource).filter(JobSource.is_active.is_(True)).all()
        run.stocks_total = len(sources)
        db.add(run)
        _init_run_job_rows(db, run.id, sources)
        _cleanup_old_job_status(db, _two_most_recent_jobs_run_ids(db))

        run_id = run.id
        owner_id = owner
    finally:
        db.close()

    refresh_worker.submit(lambda: _execute_jobs_refresh(run_id, owner_id))
    return {"run_id": run_id, "phase": "queued", "status": "started"}


def start_single_jobs_refresh_background(source_id: int) -> dict:
    """Kick off a one-off scrape for a single job source on the worker thread."""
    db = SessionLocal()
    try:
        source = db.get(JobSource, source_id)
        if source is None:
            return {"run_id": None, "phase": None, "status": "not_found"}

        owner = process_owner()
        if not lock_manager.try_acquire_lock(db, _JOBS_LOCK_NAME, owner):
            current = (
                db.query(RunLog)
                .filter(
                    RunLog.run_type == "jobs",
                    RunLog.phase.in_(("queued", "running")),
                )
                .order_by(RunLog.id.desc())
                .first()
            )
            return {
                "run_id": current.id if current else None,
                "phase": "running",
                "status": "already_running",
            }

        run = RunLog(run_type="jobs", phase="queued", started_at=utcnow(), stocks_total=1)
        db.add(run)
        db.commit()

        _init_run_job_rows(db, run.id, [source])
        _cleanup_old_job_status(db, _two_most_recent_jobs_run_ids(db))

        run_id = run.id
        owner_id = owner
        source_id_int = source.id
    finally:
        db.close()

    refresh_worker.submit(
        lambda: _execute_single_jobs_refresh(run_id, owner_id, source_id_int)
    )
    return {"run_id": run_id, "phase": "queued", "status": "started"}


def cancel_current_jobs_refresh() -> dict:
    """Flag the currently running jobs scrape for cancellation."""
    db = SessionLocal()
    try:
        current = (
            db.query(RunLog)
            .filter(
                RunLog.run_type == "jobs",
                RunLog.phase.in_(("queued", "running")),
            )
            .order_by(RunLog.id.desc())
            .first()
        )
        if current is None:
            return {"cancelled": False, "reason": "no_active_run"}
        request_cancel_for_jobs_run(current.id)
        return {
            "cancelled": True,
            "run_id": current.id,
            "phase": current.phase,
        }
    finally:
        db.close()


def run_jobs_blocking() -> RunLog:
    """Cron entry point. Blocks until the run finishes (or 4h hard cap)."""
    result = start_refresh_jobs_background()
    run_id = result.get("run_id")
    if not run_id:
        return RunLog(status="skipped")
    return run_pipeline.wait_for_run_completion(run_id)


# ---------------------------------------------------------------------------
# Test endpoint helper
# ---------------------------------------------------------------------------

async def test_source_scrape(source: JobSource) -> dict:
    """Run the configured adapter for ``source`` once without persisting.

    Used by the admin "Test" button on the source-edit form. Returns the
    same shape the cron path would record so the UI can preview the result
    before saving. Errors are caught and returned as ``status='error'``.
    """
    started = time.perf_counter()
    try:
        adapter = _adapter_for(source)
        count, raw_meta = await adapter.fetch_job_count(source)
        return {
            "status": "ok",
            "jobs_count": count,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "raw_meta": raw_meta,
        }
    except Exception as exc:
        logger.warning("Test scrape failed for source %s: %s", source.id, exc)
        return {
            "status": "error",
            "error": humanize_error(exc),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _adapter_for(source: JobSource) -> BaseJobAdapter:
    cls = ADAPTER_REGISTRY.get(source.adapter_type)
    if cls is None:
        # Distinguish "extra not installed" from "typo in the config"
        # so the user knows whether to fix YAML or run pip install.
        if source.adapter_type in PLAYWRIGHT_ADAPTER_NAMES:
            raise AdapterError(
                f"job_source {source.id}: adapter_type "
                f"'{source.adapter_type}' requires the Playwright extra. "
                "Install it with `pip install -e .[playwright]` and run "
                "`python -m playwright install chromium` once."
            )
        raise AdapterError(
            f"job_source {source.id}: unsupported adapter_type "
            f"'{source.adapter_type}'"
        )
    return cls()


def _init_run_job_rows(db: Session, run_id: int, sources: list[JobSource]) -> int:
    count = 0
    for source in sources:
        db.add(
            RunJobStatus(
                run_id=run_id,
                job_source_id=source.id,
                source_name=source.name,
                isin=source.isin,
            )
        )
        count += 1
    db.commit()
    return count


def _cleanup_old_job_status(db: Session, keep_run_ids: list[int]) -> int:
    if not keep_run_ids:
        return 0
    deleted = (
        db.query(RunJobStatus)
        .filter(~RunJobStatus.run_id.in_(keep_run_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def _two_most_recent_jobs_run_ids(db: Session) -> list[int]:
    rows = (
        db.query(RunLog.id)
        .filter(RunLog.run_type == "jobs")
        .order_by(RunLog.id.desc())
        .limit(2)
        .all()
    )
    return [r.id for r in rows]


def _get_status_row(db: Session, run_id: int, source_id: int) -> RunJobStatus | None:
    return (
        db.query(RunJobStatus)
        .filter(
            RunJobStatus.run_id == run_id,
            RunJobStatus.job_source_id == source_id,
        )
        .one_or_none()
    )


def _mark_running(row: RunJobStatus) -> None:
    row.overall_status = "running"
    row.started_at = utcnow()


def _mark_done(row: RunJobStatus, count: int, duration_ms: int) -> None:
    row.overall_status = "done"
    row.finished_at = utcnow()
    row.duration_ms = duration_ms
    row.jobs_count = count


def _mark_error(row: RunJobStatus, exc: Exception, duration_ms: int) -> None:
    row.overall_status = "error"
    row.finished_at = utcnow()
    row.duration_ms = duration_ms
    row.error = humanize_error(exc)


def _mark_remaining_cancelled(db: Session, run_id: int) -> int:
    rows = (
        db.query(RunJobStatus)
        .filter(
            RunJobStatus.run_id == run_id,
            RunJobStatus.overall_status.in_(("not_started", "running")),
        )
        .all()
    )
    now = utcnow()
    for row in rows:
        row.overall_status = "cancelled"
        if row.finished_at is None:
            row.finished_at = now
    db.commit()
    return len(rows)


def _upsert_snapshot(
    db: Session,
    *,
    source_id: int,
    snapshot_date: date_type,
    count: int,
    raw_meta: dict,
    run_id: int | None,
) -> None:
    """Idempotent UPSERT keyed on (job_source_id, snapshot_date).

    Re-running the cron on the same day overwrites instead of duplicating;
    likewise a manual scrape after the cron updates the previous row.
    """
    existing = (
        db.query(JobSnapshot)
        .filter(
            JobSnapshot.job_source_id == source_id,
            JobSnapshot.snapshot_date == snapshot_date,
        )
        .one_or_none()
    )
    if existing is None:
        db.add(
            JobSnapshot(
                job_source_id=source_id,
                snapshot_date=snapshot_date,
                jobs_count=count,
                recorded_at=utcnow(),
                run_id=run_id,
                raw_meta=raw_meta or {},
            )
        )
    else:
        existing.jobs_count = count
        existing.recorded_at = utcnow()
        existing.run_id = run_id
        existing.raw_meta = raw_meta or {}
        db.add(existing)


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------


async def _execute_jobs_refresh(run_id: int, owner: str) -> None:
    """Process every active job source for the given run."""
    async with run_pipeline.run_context(
        run_id, owner,
        lock_name=_JOBS_LOCK_NAME,
        cancel_cleanup_fn=_mark_remaining_cancelled,
    ) as state:
        if state.get("run_missing"):
            return
        db: Session = state["db"]
        errors: list[str] = state["errors"]

        cancel_check = lambda: is_jobs_cancel_requested(run_id)  # noqa: E731

        run = db.get(RunLog, run_id)
        sources = db.query(JobSource).filter(JobSource.is_active.is_(True)).all()
        for source in sources:
            if cancel_check():
                state["cancelled"] = True
                break
            try:
                success = await _process_single_source(
                    db, run_id, source, errors, cancel_check=cancel_check
                )
            except run_pipeline.RunCancelled:
                state["cancelled"] = True
                break
            run.stocks_done += 1
            if success:
                run.stocks_success += 1
            else:
                run.stocks_error += 1
            db.add(run)
            lock_manager.heartbeat_lock(db, _JOBS_LOCK_NAME, owner, commit=False)
            db.commit()


async def _execute_single_jobs_refresh(
    run_id: int, owner: str, source_id: int
) -> None:
    async with run_pipeline.run_context(
        run_id, owner,
        lock_name=_JOBS_LOCK_NAME,
        cancel_cleanup_fn=_mark_remaining_cancelled,
    ) as state:
        if state.get("run_missing"):
            return
        db: Session = state["db"]
        errors: list[str] = state["errors"]

        cancel_check = lambda: is_jobs_cancel_requested(run_id)  # noqa: E731

        source = db.get(JobSource, source_id)
        run = db.get(RunLog, run_id)
        if source is None:
            errors.append(f"source {source_id} vanished before scrape")
            return
        if cancel_check():
            state["cancelled"] = True
            return

        try:
            success = await _process_single_source(
                db, run_id, source, errors, cancel_check=cancel_check
            )
        except run_pipeline.RunCancelled:
            state["cancelled"] = True
            success = False

        run.stocks_done = 1
        if success:
            run.stocks_success = 1
        else:
            run.stocks_error = 1
        db.add(run)
        lock_manager.heartbeat_lock(db, _JOBS_LOCK_NAME, owner, commit=False)
        db.commit()


async def _process_single_source(
    db: Session,
    run_id: int,
    source: JobSource,
    errors: list[str],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> bool:
    """Scrape one source with retry; persist snapshot + status row."""
    row = _get_status_row(db, run_id, source.id)
    if row is None:
        row = RunJobStatus(
            run_id=run_id,
            job_source_id=source.id,
            source_name=source.name,
            isin=source.isin,
        )
        db.add(row)

    _mark_running(row)
    db.add(row)
    db.commit()

    started = time.perf_counter()
    try:
        adapter = _adapter_for(source)
        count, raw_meta = await run_pipeline.retry_with_cancel(
            lambda: adapter.fetch_job_count(source),
            cancel_check=cancel_check,
            no_retry_exceptions=(AdapterError,),
        )
    except run_pipeline.RunCancelled:
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        _mark_error(row, exc, duration_ms)
        db.add(row)
        db.commit()
        errors.append(f"source {source.id} ({source.name}): {exc}")
        return False

    duration_ms = int((time.perf_counter() - started) * 1000)
    snapshot_date = utcnow().date()
    _upsert_snapshot(
        db,
        source_id=source.id,
        snapshot_date=snapshot_date,
        count=count,
        raw_meta=raw_meta,
        run_id=run_id,
    )
    _mark_done(row, count, duration_ms)
    db.add(row)
    db.commit()
    return True



__all__ = [
    "JobsRefreshCancelled",
    "_JOBS_LOCK_NAME",
    "cancel_current_jobs_refresh",
    "is_jobs_cancel_requested",
    "request_cancel_for_jobs_run",
    "run_jobs_blocking",
    "start_refresh_jobs_background",
    "start_single_jobs_refresh_background",
    "test_source_scrape",
]
