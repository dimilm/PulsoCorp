"""Run-level concurrency primitives for the refresh pipeline.

This module sits between the low-level atomic-lock primitives in
`lock_manager.py` and the run executor in `refresh_runner.py`:

* It owns the `_LOCK_NAME` constant shared between the bulk and single
  refresh entrypoints (so they cannot overlap each other).
* It maintains the in-memory cancellation registry that the request
  thread uses to flag a run for abort and the worker thread polls
  between stocks.
* It re-exports the convenience wrappers (`_heartbeat`,
  `recover_stale_locks`) so callers don't need to import the lower-level
  module directly.
"""
from __future__ import annotations

import threading

from sqlalchemy.orm import Session

from app.services import lock_manager
from app.services.lock_manager import LOCK_HEARTBEAT_TTL  # re-export for back-compat
from app.services.lock_manager import is_lock_stale  # re-export for back-compat
from app.services.lock_manager import process_owner  # re-export for back-compat

_LOCK_NAME = "daily_refresh"


# Cancellation registry for in-flight refresh runs. The set is shared between
# the FastAPI request thread (which writes via `cancel_current_refresh`) and
# the refresh worker thread (which reads via `is_cancel_requested`), so all
# access is guarded by a lock.
_cancel_lock = threading.Lock()
_cancelled_run_ids: set[int] = set()


class RefreshCancelled(BaseException):
    """Internal abort signal raised from within the refresh pipeline.

    Inherits from `BaseException` (not `Exception`) so it bypasses the broad
    `except Exception` blocks in `_process_single_stock` and propagates
    cleanly up to the run-level loop.
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


def heartbeat(db: Session, owner: str, *, commit: bool = True) -> None:
    """Renew the heartbeat for the current lock owner.

    Thin wrapper around `lock_manager.heartbeat_lock` so call sites don't
    have to know about the underlying lock name.
    """
    lock_manager.heartbeat_lock(db, _LOCK_NAME, owner, commit=commit)


def recover_stale_locks() -> None:
    """Release locks whose owner crashed.

    Called from the FastAPI lifespan on every startup. Any refresh that
    was interrupted is also marked as `phase=finished / status=error` so
    the UI does not keep showing a perpetually-running run.
    """
    lock_manager.recover_stale_locks(_LOCK_NAME)


__all__ = [
    "_LOCK_NAME",
    "LOCK_HEARTBEAT_TTL",
    "RefreshCancelled",
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
