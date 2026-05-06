"""Shared primitives for the market-data refresh and job-scrape pipelines.

Both pipelines need the same mechanics:

* A thread-safe cancellation registry keyed by ``run_id`` (RunLog.id values
  are globally unique, so one unified registry covers both run types without
  risk of cross-contamination).
* An exponential-backoff retry loop that checks for cancellation between
  attempts.
* An async context manager that wraps the per-run lifecycle (phase
  transitions, lock release, cancel cleanup, session teardown).
* A blocking cron-loop that polls ``RunLog.phase`` until the worker finishes.
* A tiny helper that reliably returns an ``AppSettings`` row for ``id=1``.

``refresh_runner`` and ``jobs_service`` delegate to these primitives instead
of duplicating the logic. ``refresh_lock`` re-exports the cancel primitives
as named aliases so that existing call sites and tests continue to work
without change.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.run_log import RunLog
from app.models.settings import AppSettings
from app.services import lock_manager

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRY_DELAYS: tuple[int, ...] = (0, 2, 4, 8)

# ---------------------------------------------------------------------------
# Unified cancellation registry
# ---------------------------------------------------------------------------

_cancel_lock = threading.Lock()
_cancelled_run_ids: set[int] = set()


class RunCancelled(BaseException):
    """Internal abort signal raised from within a pipeline run.

    Inherits from ``BaseException`` (not ``Exception``) so it propagates
    cleanly through broad ``except Exception`` blocks in per-item handlers
    and reaches the run-level loop without being swallowed.
    """


def request_cancel_for_run(run_id: int) -> None:
    with _cancel_lock:
        _cancelled_run_ids.add(run_id)


def is_cancel_requested(run_id: int) -> bool:
    with _cancel_lock:
        return run_id in _cancelled_run_ids


def clear_cancel(run_id: int) -> None:
    with _cancel_lock:
        _cancelled_run_ids.discard(run_id)


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def retry_with_cancel(
    fn: Callable[[], Awaitable[T]],
    *,
    cancel_check: Callable[[], bool] | None = None,
    no_retry_exceptions: tuple[type[Exception], ...] = (),
) -> T:
    """Call *fn* up to ``len(_RETRY_DELAYS)`` times with exponential back-off.

    Parameters
    ----------
    fn:
        Async callable to attempt.
    cancel_check:
        Optional callable returning ``True`` when the run has been flagged
        for cancellation. Checked before each attempt and, during the
        back-off sleep, every 0.5 s. Raises ``RunCancelled`` when triggered.
    no_retry_exceptions:
        Exception types that are deterministic (e.g. configuration errors)
        and should abort the retry loop immediately. Pass
        ``(AdapterError,)`` for the job-scrape pipeline.
    """
    last_exc: Exception | None = None
    for delay in _RETRY_DELAYS:
        if cancel_check and cancel_check():
            raise RunCancelled()
        if delay:
            slept = 0.0
            while slept < delay:
                if cancel_check and cancel_check():
                    raise RunCancelled()
                step = min(0.5, delay - slept)
                await asyncio.sleep(step)
                slept += step
        try:
            return await fn()
        except RunCancelled:
            raise
        except no_retry_exceptions as exc:
            raise exc
        except Exception as exc:
            last_exc = exc
    if last_exc is None:  # pragma: no cover - logically unreachable
        raise RuntimeError("retry_with_cancel failed without capturing exception")
    raise last_exc


# ---------------------------------------------------------------------------
# Per-run lifecycle context manager
# ---------------------------------------------------------------------------

@asynccontextmanager
async def run_context(
    run_id: int,
    owner: str,
    *,
    lock_name: str,
    cancel_cleanup_fn: Callable[[Session, int], object] | None = None,
) -> AsyncIterator[dict]:
    """Async context manager wrapping the full lifecycle of one pipeline run.

    Provides a mutable ``state`` dict to the body with keys:

    * ``db`` — open ``Session``; the body must not close it.
    * ``errors`` — ``list[str]``; the body appends human-readable error
      descriptions.
    * ``cancelled`` — ``bool``; the body sets this to ``True`` on cancel.
    * ``run_missing`` — ``bool``; set when the RunLog row cannot be found;
      the body should return immediately when this is ``True``.

    On exit (normal, cancelled, or unexpectedly raised):

    1. ``RunLog.phase`` is set to ``"finished"`` and timing counters are
       recorded.
    2. When ``cancelled``, ``cancel_cleanup_fn(db, run_id)`` is called first
       (if provided) to mark remaining in-flight items as cancelled.
    3. The named lock is released via ``lock_manager.release_lock``.
    4. The session is closed.
    5. The cancel flag is cleared from the registry via ``clear_cancel``.

    Parameters
    ----------
    run_id:
        Primary key of the ``RunLog`` row this pipeline run corresponds to.
    owner:
        Process-owner string used as the lock owner identifier.
    lock_name:
        Name of the ``JobLock`` row held by this run.
    cancel_cleanup_fn:
        Optional ``(db, run_id) -> Any`` callable invoked when the run was
        cancelled before all items were processed. Typically marks remaining
        child rows (``RunStockStatus`` / ``RunJobStatus``) as ``"cancelled"``.
        The callable may commit internally; any unflushed state on the ``run``
        object at that point is written to the DB as part of that commit.
    """
    db = SessionLocal()
    started = time.perf_counter()
    state: dict = {
        "db": db,
        "errors": [],
        "cancelled": False,
        "run_missing": False,
    }
    try:
        run = db.get(RunLog, run_id)
        if run is None:
            logger.error("Pipeline run %s vanished before execution", run_id)
            state["run_missing"] = True
            yield state
            return
        run.phase = "running"
        db.add(run)
        db.commit()

        try:
            yield state
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Pipeline run %s crashed: %s", run_id, exc)
            state["errors"].append(f"run-crash: {exc}")
    finally:
        if not state.get("run_missing"):
            run = db.get(RunLog, run_id)
            if run is not None:
                run.phase = "finished"
                run.finished_at = utcnow()
                run.duration_seconds = int(time.perf_counter() - started)
                if state["cancelled"]:
                    if cancel_cleanup_fn is not None:
                        cancel_cleanup_fn(db, run_id)
                    run.status = "cancelled"
                    cancel_note = "Abgebrochen durch Benutzer"
                    run.error_details = (
                        "\n".join([cancel_note, *state["errors"]])
                        if state["errors"]
                        else cancel_note
                    )
                else:
                    run.status = "ok" if not state["errors"] else "partial_error"
                    run.error_details = (
                        "\n".join(state["errors"]) if state["errors"] else None
                    )
                db.add(run)
            db.commit()
            lock_manager.release_lock(db, lock_name, owner)
        db.close()
        clear_cancel(run_id)


# ---------------------------------------------------------------------------
# Cron blocking helper
# ---------------------------------------------------------------------------

def wait_for_run_completion(
    run_id: int,
    *,
    deadline_seconds: float = 4 * 60 * 60,
    poll_interval: float = 2.0,
) -> RunLog:
    """Block until ``run_id`` reaches ``phase="finished"`` or the deadline.

    Designed for APScheduler cron jobs that run on their own thread and need
    to wait for the worker-thread pipeline to finish before returning a
    result. Opens and closes a fresh ``Session`` per poll so it always reads
    committed state.

    Returns the final ``RunLog``; on deadline expiry returns a synthetic
    error row so the caller always has something to log.
    """
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        db = SessionLocal()
        try:
            row = db.get(RunLog, run_id)
            if row is None or row.phase == "finished":
                return row or RunLog(id=run_id, status="error")
        finally:
            db.close()
        time.sleep(poll_interval)
    logger.warning("Pipeline run %s exceeded the blocking deadline", run_id)
    return RunLog(id=run_id, status="error")


# ---------------------------------------------------------------------------
# AppSettings helper
# ---------------------------------------------------------------------------

def get_or_create_app_settings(db: Session) -> AppSettings:
    """Return the singleton ``AppSettings`` row (id=1), creating it if absent."""
    settings = db.get(AppSettings, 1)
    if settings is None:
        settings = AppSettings(id=1)
        db.add(settings)
        db.commit()
    return settings
