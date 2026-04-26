"""Backwards-compatible facade for the (now split) refresh subsystem.

The actual implementation lives in three focused modules:

* `app.services.refresh_lock` – run-level lock + cancellation primitives.
* `app.services.refresh_runner` – pipeline executor and entry points.
* `app.services.cron_scheduler` – APScheduler wiring.

This module re-exports everything callers (routers, lifespan, tests) used
to import from `scheduler_service` so the refactor stays a no-op for
consumers. Prefer importing from the focused modules in new code.
"""
from __future__ import annotations

from app.services import lock_manager, refresh_lock, refresh_runner
from app.services.cron_scheduler import (
    _job,
    _schedule,
    scheduler,
    shutdown_scheduler,
    start_scheduler,
    sync_scheduler_from_db,
)
from app.services.refresh_lock import (
    LOCK_HEARTBEAT_TTL as _LOCK_HEARTBEAT_TTL,
)
from app.services.refresh_lock import RefreshCancelled as _RefreshCancelled
from app.services.refresh_lock import (
    _LOCK_NAME,
    _cancel_lock,
    _cancelled_run_ids,
    is_cancel_requested,
    request_cancel_for_run,
)
from app.services.refresh_lock import clear_cancel as _clear_cancel
from app.services.refresh_lock import heartbeat as _heartbeat
from app.services.refresh_lock import is_lock_stale as _is_lock_stale
from app.services.refresh_lock import process_owner as _process_owner
from app.services.refresh_lock import recover_stale_locks
from app.services.refresh_runner import (
    _execute_refresh,
    _execute_single_refresh,
    _flag_market_error,
    _process_market_steps,
    _process_single_stock,
    _RETRY_DELAYS,
    _retry,
    cancel_current_refresh,
    refresh_worker,
    run_refresh_all_blocking,
    start_refresh_all_background,
    start_single_refresh_background,
)
from app.providers.market.yfinance_provider import YFinanceProvider

__all__ = [
    "LOCK_HEARTBEAT_TTL",
    "YFinanceProvider",
    "_LOCK_HEARTBEAT_TTL",
    "_LOCK_NAME",
    "_RefreshCancelled",
    "_RETRY_DELAYS",
    "_cancel_lock",
    "_cancelled_run_ids",
    "_clear_cancel",
    "_execute_refresh",
    "_execute_single_refresh",
    "_flag_market_error",
    "_heartbeat",
    "_is_lock_stale",
    "_job",
    "_process_market_steps",
    "_process_owner",
    "_process_single_stock",
    "_retry",
    "_schedule",
    "cancel_current_refresh",
    "is_cancel_requested",
    "lock_manager",
    "refresh_lock",
    "refresh_runner",
    "refresh_worker",
    "recover_stale_locks",
    "request_cancel_for_run",
    "run_refresh_all_blocking",
    "scheduler",
    "shutdown_scheduler",
    "start_refresh_all_background",
    "start_scheduler",
    "start_single_refresh_background",
    "sync_scheduler_from_db",
]

# Re-export the public TTL name as well, for callers using the "non-private"
# alias.
LOCK_HEARTBEAT_TTL = _LOCK_HEARTBEAT_TTL
