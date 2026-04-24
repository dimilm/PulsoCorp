"""Tests for the manual refresh-cancel pipeline.

Covers the cancellation registry, the `cancel_current_refresh` entrypoint,
the `mark_remaining_cancelled` helper, and that `_retry` honours the cancel
flag between back-off attempts.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.run_log import RunLog, RunStockStatus
from app.services import scheduler_service as ss
from app.services.run_status_service import mark_remaining_cancelled


@pytest.fixture(autouse=True)
def _reset_state():
    """Drop run/state rows + clear the in-memory cancel registry per test."""
    db = SessionLocal()
    try:
        db.query(RunStockStatus).delete()
        db.query(RunLog).delete()
        db.commit()
    finally:
        db.close()
    with ss._cancel_lock:
        ss._cancelled_run_ids.clear()
    yield
    with ss._cancel_lock:
        ss._cancelled_run_ids.clear()


def _make_run(phase: str = "running") -> int:
    db = SessionLocal()
    try:
        run = RunLog(phase=phase, started_at=utcnow())
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


def _make_status(run_id: int, isin: str, *, overall: str = "not_started") -> None:
    db = SessionLocal()
    try:
        db.add(
            RunStockStatus(
                run_id=run_id,
                isin=isin,
                stock_name=f"Stock {isin}",
                overall_status=overall,
            )
        )
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Registry semantics
# ---------------------------------------------------------------------------


def test_request_and_clear_cancel_round_trip() -> None:
    assert ss.is_cancel_requested(42) is False
    ss.request_cancel_for_run(42)
    assert ss.is_cancel_requested(42) is True
    ss._clear_cancel(42)
    assert ss.is_cancel_requested(42) is False


# ---------------------------------------------------------------------------
# cancel_current_refresh entrypoint
# ---------------------------------------------------------------------------


def test_cancel_current_refresh_without_active_run() -> None:
    result = ss.cancel_current_refresh()
    assert result == {"cancelled": False, "reason": "no_active_run"}


def test_cancel_current_refresh_flags_running_run() -> None:
    run_id = _make_run(phase="running")
    result = ss.cancel_current_refresh()
    assert result["cancelled"] is True
    assert result["run_id"] == run_id
    assert result["phase"] == "running"
    assert ss.is_cancel_requested(run_id) is True


def test_cancel_current_refresh_ignores_finished_runs() -> None:
    _make_run(phase="finished")
    result = ss.cancel_current_refresh()
    assert result["cancelled"] is False


# ---------------------------------------------------------------------------
# mark_remaining_cancelled
# ---------------------------------------------------------------------------


def test_mark_remaining_cancelled_only_touches_open_rows() -> None:
    run_id = _make_run()
    _make_status(run_id, "OPEN1", overall="not_started")
    _make_status(run_id, "OPEN2", overall="running")
    _make_status(run_id, "DONE1", overall="done")
    _make_status(run_id, "ERR1", overall="error")

    db = SessionLocal()
    try:
        updated = mark_remaining_cancelled(db, run_id)
        assert updated == 2
        rows = (
            db.query(RunStockStatus)
            .filter(RunStockStatus.run_id == run_id)
            .order_by(RunStockStatus.isin.asc())
            .all()
        )
        by_isin = {r.isin: r for r in rows}
        assert by_isin["OPEN1"].overall_status == "cancelled"
        assert by_isin["OPEN1"].finished_at is not None
        assert by_isin["OPEN2"].overall_status == "cancelled"
        # Steps that were still open also get the cancelled marker.
        assert by_isin["OPEN1"].symbol_status == "cancelled"
        assert by_isin["OPEN1"].quote_status == "cancelled"
        assert by_isin["OPEN1"].metrics_status == "cancelled"
        # Already-finished rows stay untouched.
        assert by_isin["DONE1"].overall_status == "done"
        assert by_isin["ERR1"].overall_status == "error"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# _retry cancel-aware behaviour
# ---------------------------------------------------------------------------


def test_retry_aborts_when_cancel_flag_is_set() -> None:
    """Once the cancel callback returns True, `_retry` raises immediately."""

    cancelled_after_first = {"called": 0}

    async def always_failing():
        cancelled_after_first["called"] += 1
        raise RuntimeError("boom")

    cancel_flag = {"value": False}

    def cancel_check() -> bool:
        # Trip the flag after the first attempt so we exercise the
        # between-retry check rather than the very first iteration.
        if cancelled_after_first["called"] >= 1:
            cancel_flag["value"] = True
        return cancel_flag["value"]

    async def runner():
        await ss._retry(always_failing, cancel_check=cancel_check)

    with pytest.raises(ss._RefreshCancelled):
        asyncio.run(runner())
    # First attempt happened, then cancel kicked in before the next retry.
    assert cancelled_after_first["called"] == 1


def test_retry_without_cancel_check_propagates_last_error() -> None:
    async def always_failing():
        raise ValueError("nope")

    async def runner():
        await ss._retry(always_failing)

    with pytest.raises(ValueError):
        asyncio.run(runner())
