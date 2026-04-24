from __future__ import annotations

import asyncio
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Awaitable, Callable, TypeVar

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.run_log import JobLock, RunLog, RunStockStatus
from app.models.settings import AppSettings
from app.models.stock import MarketData, Stock
from app.providers.market.yfinance_provider import YFinanceProvider
from app.services.market_service import MarketService
from app.services.refresh_worker import worker as refresh_worker
from app.services.run_status_service import (
    cleanup_old_run_status,
    get_status_row,
    humanize_error,
    init_run_stocks,
    mark_remaining_cancelled,
    mark_step_done,
    mark_step_error,
    mark_step_running,
    mark_stock_finished,
    mark_stock_running,
    two_most_recent_run_ids,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

T = TypeVar("T")

_RETRY_DELAYS = (0, 2, 4, 8)
_LOCK_NAME = "daily_refresh"
# After this many seconds without a heartbeat the lock is considered stale and
# may be reclaimed. The refresh writes a heartbeat after every stock; the
# pipeline only does symbol/quote/metrics now, so 5 minutes is a generous
# margin even for slow upstream APIs.
_LOCK_HEARTBEAT_TTL = timedelta(minutes=5)

# Cancellation registry for in-flight refresh runs. The set is shared between
# the FastAPI request thread (which writes via `cancel_current_refresh`) and
# the refresh worker thread (which reads via `is_cancel_requested`), so all
# access is guarded by a lock.
_cancel_lock = threading.Lock()
_cancelled_run_ids: set[int] = set()


class _RefreshCancelled(BaseException):
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


def _clear_cancel(run_id: int) -> None:
    with _cancel_lock:
        _cancelled_run_ids.discard(run_id)


def _process_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _is_lock_stale(lock: JobLock) -> bool:
    if not lock.locked:
        return False
    if lock.heartbeat_at is None:
        # Old row from before the TTL columns existed -> treat as stale.
        return True
    return utcnow() - lock.heartbeat_at > _LOCK_HEARTBEAT_TTL


def _heartbeat(db: Session, owner: str) -> None:
    """Renew the heartbeat for the current lock owner."""
    lock = db.get(JobLock, _LOCK_NAME)
    if lock is None or lock.owner != owner:
        return
    lock.heartbeat_at = utcnow()
    db.add(lock)
    db.commit()


def recover_stale_locks() -> None:
    """Release locks whose owner crashed.

    Called from the FastAPI lifespan on every startup. Any refresh that was
    interrupted is also marked as 'finished/error' so the UI does not keep
    showing a perpetually-running run.
    """
    db = SessionLocal()
    try:
        lock = db.get(JobLock, _LOCK_NAME)
        if lock and _is_lock_stale(lock):
            logger.warning(
                "Reclaiming stale refresh lock (owner=%s, heartbeat=%s)",
                lock.owner,
                lock.heartbeat_at,
            )
            lock.locked = False
            lock.owner = None
            db.add(lock)
            for stuck in (
                db.query(RunLog).filter(RunLog.phase.in_(("queued", "running"))).all()
            ):
                stuck.phase = "finished"
                stuck.status = "error"
                stuck.finished_at = utcnow()
                stuck.error_details = (stuck.error_details or "") + "\nrecovered after crash"
                db.add(stuck)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------

def start_refresh_all_background() -> dict:
    """Prepare a refresh run synchronously, then hand the work off to the worker.

    Returns a small dict with `run_id`, `phase` and `status` so that the UI can
    immediately navigate to the runs view and start polling for updates. This
    function is purposely *not* async: it must complete entirely on the calling
    request thread (no awaits) so the FastAPI event loop is free to serve other
    requests while the refresh runs on the dedicated worker.
    """
    db = SessionLocal()
    try:
        app_settings = db.get(AppSettings, 1) or AppSettings(id=1)
        db.add(app_settings)
        db.commit()

        if not app_settings.update_weekends and utcnow().weekday() >= 5:
            run = RunLog(
                phase="finished",
                status="skipped",
                started_at=utcnow(),
                finished_at=utcnow(),
                error_details="Weekend skip active",
            )
            db.add(run)
            db.commit()
            return {"run_id": run.id, "phase": "finished", "status": "skipped"}

        lock = db.get(JobLock, _LOCK_NAME) or JobLock(name=_LOCK_NAME, locked=False)
        if lock.locked and not _is_lock_stale(lock):
            current = (
                db.query(RunLog)
                .filter(RunLog.phase.in_(("queued", "running")))
                .order_by(RunLog.id.desc())
                .first()
            )
            return {
                "run_id": current.id if current else None,
                "phase": "running",
                "status": "already_running",
            }
        if lock.locked:
            logger.warning(
                "Stale refresh lock detected (owner=%s, heartbeat=%s) – reclaiming",
                lock.owner,
                lock.heartbeat_at,
            )

        owner = _process_owner()
        now = utcnow()
        lock.locked = True
        lock.owner = owner
        lock.acquired_at = now
        lock.heartbeat_at = now
        db.add(lock)

        run = RunLog(phase="queued", started_at=utcnow())
        db.add(run)
        db.commit()

        stocks = db.query(Stock).all()
        run.stocks_total = len(stocks)
        db.add(run)
        init_run_stocks(db, run.id, stocks)

        cleanup_old_run_status(db, two_most_recent_run_ids(db))

        run_id = run.id
        owner_id = owner
    finally:
        db.close()

    refresh_worker.submit(lambda: _execute_refresh(run_id, owner_id))
    return {"run_id": run_id, "phase": "queued", "status": "started"}


def start_single_refresh_background(isin: str) -> dict:
    """Kick off a market-data refresh for a single stock on the worker thread.

    Mirrors `start_refresh_all_background` but creates a `RunLog` with
    `stocks_total=1`. The pipeline only runs the market-data steps
    (symbol/quote/metrics) – the AI agents have their own per-stock entrypoint
    on the detail page.

    Reuses the shared `_LOCK_NAME` so a single-stock refresh cannot overlap a
    bulk refresh (and vice versa); when the lock is already held the caller
    receives `status="already_running"` and can point the user at the existing
    run.
    """
    isin_upper = isin.upper()
    db = SessionLocal()
    try:
        stock = db.get(Stock, isin_upper)
        if stock is None:
            return {"run_id": None, "phase": None, "status": "not_found"}

        lock = db.get(JobLock, _LOCK_NAME) or JobLock(name=_LOCK_NAME, locked=False)
        if lock.locked and not _is_lock_stale(lock):
            current = (
                db.query(RunLog)
                .filter(RunLog.phase.in_(("queued", "running")))
                .order_by(RunLog.id.desc())
                .first()
            )
            return {
                "run_id": current.id if current else None,
                "phase": "running",
                "status": "already_running",
            }
        if lock.locked:
            logger.warning(
                "Stale refresh lock detected (owner=%s, heartbeat=%s) – reclaiming",
                lock.owner,
                lock.heartbeat_at,
            )

        owner = _process_owner()
        now = utcnow()
        lock.locked = True
        lock.owner = owner
        lock.acquired_at = now
        lock.heartbeat_at = now
        db.add(lock)

        run = RunLog(phase="queued", started_at=utcnow(), stocks_total=1)
        db.add(run)
        db.commit()

        init_run_stocks(db, run.id, [stock])
        cleanup_old_run_status(db, two_most_recent_run_ids(db))

        run_id = run.id
        owner_id = owner
    finally:
        db.close()

    refresh_worker.submit(lambda: _execute_single_refresh(run_id, owner_id, isin_upper))
    return {"run_id": run_id, "phase": "queued", "status": "started"}


def cancel_current_refresh() -> dict:
    """Flag the currently running refresh for cancellation.

    The actual abort happens inside `_execute_refresh` between stocks (and
    between retries within a stock), so the call returns immediately. The UI
    will observe `phase == "finished"` and `status == "cancelled"` once the
    in-flight stock finishes processing.
    """
    db = SessionLocal()
    try:
        current = (
            db.query(RunLog)
            .filter(RunLog.phase.in_(("queued", "running")))
            .order_by(RunLog.id.desc())
            .first()
        )
        if current is None:
            return {"cancelled": False, "reason": "no_active_run"}
        request_cancel_for_run(current.id)
        return {
            "cancelled": True,
            "run_id": current.id,
            "phase": current.phase,
        }
    finally:
        db.close()


def run_refresh_all_blocking() -> RunLog:
    """Cron entrypoint. Schedules the refresh on the worker and blocks until done.

    APScheduler runs jobs on its own thread, so blocking here is fine and does
    not affect the FastAPI loop. The blocking is implemented by waiting on the
    future returned by the worker; we sleep on `RunLog.phase` as a fallback so
    we never hold the cron thread forever if the worker dies.
    """
    import time as _time

    result = start_refresh_all_background()
    run_id = result.get("run_id")
    if not run_id:
        return RunLog(status="skipped")
    deadline = _time.time() + 60 * 60 * 4  # 4h hard cap
    while _time.time() < deadline:
        check = SessionLocal()
        try:
            row = check.get(RunLog, run_id)
            if row is None or row.phase == "finished":
                return row or RunLog(id=run_id, status="error")
        finally:
            check.close()
        _time.sleep(2)
    logger.warning("Refresh run %s exceeded the cron blocking deadline", run_id)
    return RunLog(id=run_id, status="error")


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------

async def _execute_refresh(run_id: int, owner: str) -> None:
    """Process every stock for `run_id`, writing live progress to the DB."""
    db = SessionLocal()
    started = time.perf_counter()
    errors: list[str] = []
    cancelled = False
    try:
        run = db.get(RunLog, run_id)
        if not run:
            logger.error("Refresh run %s vanished before execution", run_id)
            return
        run.phase = "running"
        db.add(run)
        db.commit()

        market_service = MarketService(YFinanceProvider())

        cancel_check = lambda: is_cancel_requested(run_id)  # noqa: E731

        stocks = db.query(Stock).all()
        for stock in stocks:
            if cancel_check():
                cancelled = True
                break
            try:
                success = await _process_single_stock(
                    db,
                    run_id,
                    stock,
                    market_service,
                    errors,
                    cancel_check=cancel_check,
                )
            except _RefreshCancelled:
                cancelled = True
                break
            run.stocks_done += 1
            if success:
                run.stocks_success += 1
            else:
                run.stocks_error += 1
            db.add(run)
            db.commit()
            # Heartbeat once per stock so a crash detector can tell whether the
            # process is still alive even on long-running runs.
            _heartbeat(db, owner)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Refresh run %s crashed: %s", run_id, exc)
        errors.append(f"run-crash: {exc}")
    finally:
        run = db.get(RunLog, run_id)
        if run is not None:
            run.phase = "finished"
            run.finished_at = utcnow()
            run.duration_seconds = int(time.perf_counter() - started)
            if cancelled:
                mark_remaining_cancelled(db, run_id)
                run.status = "cancelled"
                cancel_note = "Abgebrochen durch Benutzer"
                run.error_details = (
                    "\n".join([cancel_note, *errors]) if errors else cancel_note
                )
            else:
                run.status = "ok" if not errors else "partial_error"
                run.error_details = "\n".join(errors) if errors else None
            db.add(run)
        lock = db.get(JobLock, _LOCK_NAME)
        if lock is not None:
            # Only release the lock if we actually own it; otherwise leave it
            # alone so the rightful owner / recovery code can deal with it.
            if lock.owner in (None, owner):
                lock.locked = False
                lock.owner = None
                lock.heartbeat_at = None
                db.add(lock)
        db.commit()
        db.close()
        _clear_cancel(run_id)


async def _execute_single_refresh(run_id: int, owner: str, isin: str) -> None:
    """Process a single stock for `run_id` (market data pipeline only).

    Mirrors `_execute_refresh` but only touches one stock. AI evaluation is
    triggered separately via the agents panel on the detail page.
    """
    db = SessionLocal()
    started = time.perf_counter()
    errors: list[str] = []
    cancelled = False
    try:
        run = db.get(RunLog, run_id)
        if not run:
            logger.error("Single refresh run %s vanished before execution", run_id)
            return
        run.phase = "running"
        db.add(run)
        db.commit()

        market_service = MarketService(YFinanceProvider())
        cancel_check = lambda: is_cancel_requested(run_id)  # noqa: E731

        stock = db.get(Stock, isin)
        if stock is None:
            errors.append(f"{isin}: stock vanished before refresh")
        elif cancel_check():
            cancelled = True
        else:
            try:
                _, success = await _process_market_steps(
                    db,
                    run_id,
                    stock,
                    market_service,
                    errors,
                    cancel_check=cancel_check,
                )
            except _RefreshCancelled:
                cancelled = True
                success = False
            run.stocks_done = 1
            if success:
                run.stocks_success = 1
                row = get_status_row(db, run_id, stock.isin)
                if row is not None and row.overall_status == "running":
                    mark_stock_finished(row, success=True)
                    db.add(row)
            else:
                run.stocks_error = 1
            db.add(run)
            db.commit()
            _heartbeat(db, owner)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Single refresh run %s crashed: %s", run_id, exc)
        errors.append(f"run-crash: {exc}")
    finally:
        run = db.get(RunLog, run_id)
        if run is not None:
            run.phase = "finished"
            run.finished_at = utcnow()
            run.duration_seconds = int(time.perf_counter() - started)
            if cancelled:
                mark_remaining_cancelled(db, run_id)
                run.status = "cancelled"
                cancel_note = "Abgebrochen durch Benutzer"
                run.error_details = (
                    "\n".join([cancel_note, *errors]) if errors else cancel_note
                )
            else:
                run.status = "ok" if not errors else "partial_error"
                run.error_details = "\n".join(errors) if errors else None
            db.add(run)
        lock = db.get(JobLock, _LOCK_NAME)
        if lock is not None and lock.owner in (None, owner):
            lock.locked = False
            lock.owner = None
            lock.heartbeat_at = None
            db.add(lock)
        db.commit()
        db.close()
        _clear_cancel(run_id)


async def _process_market_steps(
    db: Session,
    run_id: int,
    stock: Stock,
    market: MarketService,
    errors: list[str],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[RunStockStatus | None, bool]:
    """Run symbol → quote → metrics → persist for a single stock.

    Returns `(status_row, success)`. The caller is responsible for flipping
    `mark_stock_finished` once it is done with the row. On failure the row is
    already marked finished/error and the market error is mirrored into
    `MarketData.last_status`.
    """
    row = get_status_row(db, run_id, stock.isin)
    if row is None:
        # Should not happen because we initialise rows up-front, but be safe.
        row = RunStockStatus(run_id=run_id, isin=stock.isin, stock_name=stock.name)
        db.add(row)
        db.commit()

    mark_stock_running(row)
    db.add(row)
    db.commit()

    # Step 1: resolve the symbol. No retry — the lookup is cached and either
    # the link is present or it isn't; retrying makes no observable difference.
    try:
        mark_step_running(row, "symbol")
        db.add(row)
        db.commit()
        symbol = await market.resolve_symbol(stock)
        row.resolved_symbol = symbol
        mark_step_done(row, "symbol")
        db.add(row)
        db.commit()
    except Exception as exc:
        mark_step_error(row, "symbol", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: symbol: {exc}")
        return row, False

    # Step 2: fetch the live quote (with retry).
    try:
        mark_step_running(row, "quote")
        db.add(row)
        db.commit()
        quote = await _retry(lambda: market.fetch_quote(symbol), cancel_check=cancel_check)
        mark_step_done(row, "quote")
        db.add(row)
        db.commit()
    except _RefreshCancelled:
        raise
    except Exception as exc:
        mark_step_error(row, "quote", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: quote: {exc}")
        return row, False

    # Step 3: fetch the fundamentals (with retry).
    try:
        mark_step_running(row, "metrics")
        db.add(row)
        db.commit()
        metrics_data = await _retry(
            lambda: market.fetch_metrics(symbol), cancel_check=cancel_check
        )
        mark_step_done(row, "metrics")
        db.add(row)
        db.commit()
    except _RefreshCancelled:
        raise
    except Exception as exc:
        mark_step_error(row, "metrics", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: metrics: {exc}")
        return row, False

    # Step 3b: persist market & metrics rows (cheap, no separate user-facing step).
    try:
        market.persist(db, stock, quote, metrics_data)
        db.commit()
    except Exception as exc:
        db.rollback()
        mark_step_error(row, "metrics", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: persist: {exc}")
        return row, False

    return row, True


async def _process_single_stock(
    db: Session,
    run_id: int,
    stock: Stock,
    market: MarketService,
    errors: list[str],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> bool:
    row, market_ok = await _process_market_steps(
        db, run_id, stock, market, errors, cancel_check=cancel_check
    )
    if not market_ok:
        return False

    assert row is not None  # _process_market_steps only returns None on success=False

    mark_stock_finished(row, success=True)
    db.add(row)
    db.commit()
    return True


def _flag_market_error(db: Session, isin: str, exc: Exception) -> None:
    """Mirror the failure into `MarketData.last_status` for the watchlist column."""
    row = db.get(MarketData, isin) or MarketData(isin=isin)
    row.last_status = "error"
    row.last_error = humanize_error(exc)
    db.add(row)
    db.commit()


async def _retry(
    fn: Callable[[], Awaitable[T]],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> T:
    last_exc: Exception | None = None
    for delay in _RETRY_DELAYS:
        if cancel_check and cancel_check():
            raise _RefreshCancelled()
        if delay:
            # Sleep in small slices so a cancel takes effect well before the
            # full back-off (worst case 8s) elapses.
            slept = 0.0
            while slept < delay:
                if cancel_check and cancel_check():
                    raise _RefreshCancelled()
                step = min(0.5, delay - slept)
                await asyncio.sleep(step)
                slept += step
        try:
            return await fn()
        except Exception as exc:
            last_exc = exc
    if last_exc is None:  # pragma: no cover - logically unreachable
        raise RuntimeError("retry failed without capturing exception")
    raise last_exc


# ---------------------------------------------------------------------------
# Cron scheduler wiring
# ---------------------------------------------------------------------------

def _schedule(hour: int, minute: int) -> None:
    scheduler.add_job(_job, "cron", hour=hour, minute=minute, id="daily_refresh", replace_existing=True)


def _job() -> None:
    run_refresh_all_blocking()


def sync_scheduler_from_db() -> None:
    db = SessionLocal()
    try:
        row = db.get(AppSettings, 1) or AppSettings(id=1)
        db.add(row)
        db.commit()
        _schedule(row.update_hour, row.update_minute)
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        sync_scheduler_from_db()
        return
    sync_scheduler_from_db()
    scheduler.start()
