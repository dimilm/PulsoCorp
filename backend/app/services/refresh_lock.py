"""Run-level concurrency primitives for the refresh pipeline.

This module sits between the low-level atomic-lock primitives in
`lock_manager.py` and the run executor in `refresh_runner.py`:

* It owns the ``_LOCK_NAME`` constant shared between the bulk and single
  refresh entrypoints (so they cannot overlap each other).
* It re-exports the unified cancellation registry from ``run_pipeline`` so
  callers (and existing tests) that import ``_cancel_lock``,
  ``_cancelled_run_ids``, ``request_cancel_for_run``, etc. from this module
  continue to work without any changes.
* It re-exports convenience wrappers (``heartbeat``, ``recover_stale_locks``)
  so callers don't need to import the lower-level module directly.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.services import lock_manager
from app.services.lock_manager import LOCK_HEARTBEAT_TTL  # re-export for back-compat
from app.services.lock_manager import is_lock_stale  # re-export for back-compat
from app.services.lock_manager import process_owner  # re-export for back-compat
from app.services.run_pipeline import (
    RunCancelled,
    _cancel_lock,
    _cancelled_run_ids,
    clear_cancel,
    is_cancel_requested,
    request_cancel_for_run,
)

_LOCK_NAME = "daily_refresh"

# Alias so existing imports of ``RefreshCancelled`` continue to work.
RefreshCancelled = RunCancelled


def heartbeat(db: Session, owner: str, *, commit: bool = True) -> None:
    """Renew the heartbeat for the current lock owner.

    Thin wrapper around ``lock_manager.heartbeat_lock`` so call sites don't
    need to know about the underlying lock name.
    """
    lock_manager.heartbeat_lock(db, _LOCK_NAME, owner, commit=commit)


def recover_stale_locks() -> None:
    """Release locks whose owner crashed.

    Called from the FastAPI lifespan on every startup. Any refresh that
    was interrupted is also marked as ``phase=finished / status=error`` so
    the UI does not keep showing a perpetually-running run.

    Only finalises ``RunLog`` rows with ``run_type='market'`` (or no
    ``run_type``) so the jobs-specific recovery in ``jobs_service`` is not
    accidentally triggered.
    """
    lock_manager.recover_stale_locks(_LOCK_NAME, run_type="market")


__all__ = [
    "_LOCK_NAME",
    "LOCK_HEARTBEAT_TTL",
    "RefreshCancelled",
    "RunCancelled",
    "_cancel_lock",
    "_cancelled_run_ids",
    "clear_cancel",
    "heartbeat",
    "is_cancel_requested",
    "is_lock_stale",
    "process_owner",
    "recover_stale_locks",
    "request_cancel_for_run",
]
