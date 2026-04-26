"""Refresh-run executor: end-to-end pipeline for one or many stocks.

Public entry points (called from the API + cron):
* `start_refresh_all_background` – queue a bulk refresh.
* `start_single_refresh_background` – queue a one-off per-stock refresh.
* `cancel_current_refresh` – flag the active run for cancellation.
* `run_refresh_all_blocking` – cron-friendly variant that waits for
  completion before returning.

The actual work runs on the dedicated `RefreshWorker` thread; the helpers
in this module orchestrate the run lifecycle (DB row, lock, cancellation,
phase transitions) and call `MarketService` for the per-step IO.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, TypeVar

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.run_log import RunLog, RunStockStatus
from app.models.settings import AppSettings
from app.models.stock import MarketData, Stock
from app.providers.market.yfinance_provider import YFinanceProvider
from app.services import lock_manager
from app.services.market_service import MarketService
from app.services.refresh_lock import (
    RefreshCancelled,
    _LOCK_NAME,
    clear_cancel,
    heartbeat,
    is_cancel_requested,
    process_owner,
    request_cancel_for_run,
)
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

T = TypeVar("T")

_RETRY_DELAYS = (0, 2, 4, 8)


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------

def start_refresh_all_background(*, manual: bool = False) -> dict:
    """Prepare a refresh run synchronously, then hand the work off to the worker.

    Returns a small dict with `run_id`, `phase` and `status` so that the UI can
    immediately navigate to the runs view and start polling for updates. This
    function is purposely *not* async: it must complete entirely on the calling
    request thread (no awaits) so the FastAPI event loop is free to serve other
    requests while the refresh runs on the dedicated worker.

    When `manual=False` (cron path) the weekend toggle in `AppSettings` is
    honoured. Manual runs (button in the UI) always proceed — the user has
    explicitly asked for a refresh, so the weekend setting only controls the
    automatic schedule.
    """
    db = SessionLocal()
    try:
        app_settings = db.get(AppSettings, 1) or AppSettings(id=1)
        db.add(app_settings)
        db.commit()

        if (
            not manual
            and not app_settings.update_weekends
            and utcnow().weekday() >= 5
        ):
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

        owner = process_owner()
        if not lock_manager.try_acquire_lock(db, _LOCK_NAME, owner):
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

        owner = process_owner()
        if not lock_manager.try_acquire_lock(db, _LOCK_NAME, owner):
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
    not affect the FastAPI loop. The blocking is implemented by polling
    `RunLog.phase`, with a 4h hard cap so a hung worker can never pin the
    cron thread indefinitely.
    """
    import time as _time

    result = start_refresh_all_background()
    run_id = result.get("run_id")
    if not run_id:
        return RunLog(status="skipped")
    deadline = _time.time() + 60 * 60 * 4
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

@asynccontextmanager
async def _refresh_context(
    run_id: int, owner: str
) -> AsyncIterator[dict]:
    """Async context manager that wraps the per-run lifecycle.

    Both `_execute_refresh` and `_execute_single_refresh` need to:
      1. Open a Session and flip `phase=running`.
      2. Run the pipeline and collect errors / cancellation.
      3. Finalize the RunLog (`phase=finished`, status, duration), release
         the lock, close the session and clear the cancel flag — even
         when the pipeline raises.

    The context exposes a small mutable `state` dict so the `with` body
    can flip `cancelled=True` and append to `errors` without juggling
    `nonlocal` bindings. Keeping all the cleanup code here means the two
    executors stay focused on their actual work.
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
            logger.error("Refresh run %s vanished before execution", run_id)
            state["run_missing"] = True
            yield state
            return
        run.phase = "running"
        db.add(run)
        db.commit()

        try:
            yield state
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Refresh run %s crashed: %s", run_id, exc)
            state["errors"].append(f"run-crash: {exc}")
    finally:
        if not state.get("run_missing"):
            run = db.get(RunLog, run_id)
            if run is not None:
                run.phase = "finished"
                run.finished_at = utcnow()
                run.duration_seconds = int(time.perf_counter() - started)
                if state["cancelled"]:
                    mark_remaining_cancelled(db, run_id)
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
            # Release after the run row is committed so observers polling
            # the lock never see "unlocked + still running".
            lock_manager.release_lock(db, _LOCK_NAME, owner)
        db.close()
        clear_cancel(run_id)


async def _execute_refresh(
    run_id: int,
    owner: str,
    *,
    market_service: MarketService | None = None,
) -> None:
    """Process every stock for `run_id`, writing live progress to the DB.

    `market_service` is overridable so callers (cron, single-shot endpoint,
    tests) can inject a stubbed provider; the default falls back to the
    module-level YFinance binding which existing monkeypatches still target.
    """
    async with _refresh_context(run_id, owner) as state:
        if state.get("run_missing"):
            return
        db: Session = state["db"]
        errors: list[str] = state["errors"]

        if market_service is None:
            market_service = MarketService(YFinanceProvider())

        cancel_check = lambda: is_cancel_requested(run_id)  # noqa: E731

        run = db.get(RunLog, run_id)
        stocks = db.query(Stock).all()
        for stock in stocks:
            if cancel_check():
                state["cancelled"] = True
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
            except RefreshCancelled:
                state["cancelled"] = True
                break
            run.stocks_done += 1
            if success:
                run.stocks_success += 1
            else:
                run.stocks_error += 1
            db.add(run)
            # Heartbeat once per stock so a crash detector can tell whether
            # the process is still alive even on long-running runs. We piggy-
            # back on the run-counter commit to avoid a second fsync per stock.
            heartbeat(db, owner, commit=False)
            db.commit()


async def _execute_single_refresh(
    run_id: int,
    owner: str,
    isin: str,
    *,
    market_service: MarketService | None = None,
) -> None:
    """Process a single stock for `run_id` (market data pipeline only).

    Mirrors `_execute_refresh` but only touches one stock. AI evaluation is
    triggered separately via the agents panel on the detail page.
    """
    async with _refresh_context(run_id, owner) as state:
        if state.get("run_missing"):
            return
        db: Session = state["db"]
        errors: list[str] = state["errors"]

        if market_service is None:
            market_service = MarketService(YFinanceProvider())
        cancel_check = lambda: is_cancel_requested(run_id)  # noqa: E731

        stock = db.get(Stock, isin)
        run = db.get(RunLog, run_id)
        if stock is None:
            errors.append(f"{isin}: stock vanished before refresh")
            return
        if cancel_check():
            state["cancelled"] = True
            return

        try:
            _, success = await _process_market_steps(
                db,
                run_id,
                stock,
                market_service,
                errors,
                cancel_check=cancel_check,
            )
        except RefreshCancelled:
            state["cancelled"] = True
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
        heartbeat(db, owner, commit=False)
        db.commit()


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

    # Commit cadence: previously we committed once for "step running" and
    # once for "step done", giving 7+ commits per stock. We collapse the
    # transition into a single commit per step boundary by combining the
    # *next* step's "running" with the current step's "done" — the UI still
    # observes every state because each commit advances exactly one step.
    mark_stock_running(row)
    mark_step_running(row, "symbol")
    db.add(row)
    db.commit()  # commit 1: stock running + symbol running

    # Step 1: resolve the symbol. No retry — the lookup is cached and either
    # the link is present or it isn't; retrying makes no observable difference.
    try:
        symbol = await market.resolve_symbol(stock)
        row.resolved_symbol = symbol
        mark_step_done(row, "symbol")
        mark_step_running(row, "quote")
        db.add(row)
        db.commit()  # commit 2: symbol done + quote running
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
        quote = await _retry(lambda: market.fetch_quote(symbol), cancel_check=cancel_check)
        mark_step_done(row, "quote")
        mark_step_running(row, "metrics")
        db.add(row)
        db.commit()  # commit 3: quote done + metrics running
    except RefreshCancelled:
        raise
    except Exception as exc:
        mark_step_error(row, "quote", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: quote: {exc}")
        return row, False

    # Step 3: fetch the fundamentals (with retry) and persist the data.
    try:
        metrics_data = await _retry(
            lambda: market.fetch_metrics(symbol), cancel_check=cancel_check
        )
        mark_step_done(row, "metrics")
        # Persist market+metrics rows in the same transaction as the step
        # update so the UI cannot observe "metrics done" without the data.
        market.persist(db, stock, quote, metrics_data)
        db.add(row)
        db.commit()  # commit 4: metrics done + persisted
    except RefreshCancelled:
        raise
    except Exception as exc:
        db.rollback()
        mark_step_error(row, "metrics", exc)
        mark_stock_finished(row, success=False)
        db.add(row)
        db.commit()
        _flag_market_error(db, stock.isin, exc)
        errors.append(f"{stock.isin}: metrics: {exc}")
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
            raise RefreshCancelled()
        if delay:
            # Sleep in small slices so a cancel takes effect well before the
            # full back-off (worst case 8s) elapses.
            slept = 0.0
            while slept < delay:
                if cancel_check and cancel_check():
                    raise RefreshCancelled()
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
