"""Tests for weekend-skip behaviour on bulk refresh runs.

Cron-triggered runs honour the `update_weekends` toggle in `AppSettings` and
short-circuit on Saturday/Sunday with `status=skipped`. Manual runs (button in
the UI) must bypass that skip so the user always gets the refresh they asked
for, regardless of weekday.
"""
from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.models.run_log import JobLock, RunLog, RunStockStatus
from app.models.settings import AppSettings
from app.models.stock import MarketData, Metrics, Stock
from app.services import scheduler_service as ss


@pytest.fixture(autouse=True)
def _reset_state():
    db = SessionLocal()
    try:
        db.query(RunStockStatus).delete()
        db.query(RunLog).delete()
        db.query(JobLock).delete()
        db.query(MarketData).delete()
        db.query(Metrics).delete()
        db.query(Stock).filter(Stock.isin.like("TEST%")).delete()
        row = db.get(AppSettings, 1) or AppSettings(id=1)
        row.update_weekends = False
        db.add(row)
        db.commit()
    finally:
        db.close()
    yield


def _seed_stock() -> None:
    db = SessionLocal()
    try:
        db.add(Stock(isin="TEST00000099", name="Weekend Test Co", currency="EUR"))
        db.commit()
    finally:
        db.close()


_SATURDAY = dt.datetime(2026, 4, 25, 12, 0, tzinfo=dt.timezone.utc)


def test_cron_run_skips_on_weekend_when_disabled(monkeypatch) -> None:
    _seed_stock()
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)

    with patch("app.services.refresh_runner.utcnow", return_value=_SATURDAY):
        result = ss.start_refresh_all_background()

    assert result["status"] == "skipped"
    assert result["phase"] == "finished"

    db = SessionLocal()
    try:
        run = db.get(RunLog, result["run_id"])
        assert run is not None
        assert run.status == "skipped"
        assert run.error_details == "Weekend skip active"
    finally:
        db.close()


def test_manual_run_bypasses_weekend_skip(monkeypatch) -> None:
    _seed_stock()
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)

    with patch("app.services.refresh_runner.utcnow", return_value=_SATURDAY):
        result = ss.start_refresh_all_background(manual=True)

    assert result["status"] == "started"
    assert result["phase"] == "queued"

    db = SessionLocal()
    try:
        run = db.get(RunLog, result["run_id"])
        assert run is not None
        assert run.status != "skipped"
        assert run.error_details != "Weekend skip active"
    finally:
        db.close()


def test_cron_run_proceeds_on_weekend_when_enabled(monkeypatch) -> None:
    _seed_stock()
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)

    db = SessionLocal()
    try:
        row = db.get(AppSettings, 1)
        row.update_weekends = True
        db.add(row)
        db.commit()
    finally:
        db.close()

    with patch("app.services.refresh_runner.utcnow", return_value=_SATURDAY):
        result = ss.start_refresh_all_background()

    assert result["status"] == "started"
    assert result["phase"] == "queued"
