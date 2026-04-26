"""Tests for the per-stock refresh endpoint and its background pipeline.

Covers:
* `POST /stocks/{isin}/refresh` returns the new run id (no longer synchronous).
* `start_single_refresh_background` rejects calls while the lock is held.
* `_execute_single_refresh` writes per-step progress + persists market data.
* The response shape stays useful when the ISIN does not exist.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.main import app
from app.models.run_log import JobLock, RunLog, RunStockStatus
from app.models.stock import MarketData, Metrics, Stock
from app.providers.market.base import MarketProvider, MetricsData, QuoteData
from app.services import scheduler_service as ss


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


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
        db.commit()
    finally:
        db.close()
    with ss._cancel_lock:
        ss._cancelled_run_ids.clear()
    yield
    db = SessionLocal()
    try:
        db.query(RunStockStatus).delete()
        db.query(RunLog).delete()
        db.query(JobLock).delete()
        db.query(MarketData).delete()
        db.query(Metrics).delete()
        db.query(Stock).filter(Stock.isin.like("TEST%")).delete()
        db.commit()
    finally:
        db.close()


def _seed_stock(isin: str = "TEST00000001", name: str = "Single Refresh Co") -> None:
    db = SessionLocal()
    try:
        db.add(Stock(isin=isin, name=name, sector="Tech", currency="EUR"))
        db.commit()
    finally:
        db.close()


class _FakeProvider(MarketProvider):
    """Lightweight stand-in for YFinanceProvider with deterministic outputs."""

    def __init__(
        self,
        *,
        symbol: str | None = "FAKE",
        quote: QuoteData | None = None,
        metrics: MetricsData | None = None,
        quote_error: Exception | None = None,
    ) -> None:
        self._symbol = symbol
        self._quote = quote or QuoteData(current_price=42.0, day_change_pct=1.5, currency="EUR")
        self._metrics = metrics or MetricsData(pe_forward=18.0, dividend_yield_current=2.5)
        self._quote_error = quote_error

    async def resolve_symbol(self, *, isin: str, name: str | None = None, yahoo_link: str | None = None) -> str | None:
        return self._symbol

    async def fetch_quote(self, symbol: str) -> QuoteData:
        if self._quote_error is not None:
            raise self._quote_error
        return self._quote

    async def fetch_metrics(self, symbol: str) -> MetricsData:
        return self._metrics


# ---------------------------------------------------------------------------
# HTTP endpoint
# ---------------------------------------------------------------------------


def test_refresh_endpoint_returns_run_id_and_starts_run(monkeypatch) -> None:
    """The endpoint kicks off a background run and returns its id."""
    _seed_stock()
    captured: dict = {}

    def fake_start(isin: str) -> dict:
        captured["isin"] = isin
        return {"run_id": 7, "phase": "queued", "status": "started"}

    monkeypatch.setattr("app.api.v1.stocks.start_single_refresh_background", fake_start)

    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        "/api/v1/stocks/test00000001/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"run_id": 7, "phase": "queued", "status": "started"}
    assert captured["isin"] == "TEST00000001"


def test_refresh_endpoint_returns_404_for_unknown_isin() -> None:
    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        "/api/v1/stocks/TEST99999999/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# start_single_refresh_background
# ---------------------------------------------------------------------------


def test_start_single_refresh_creates_run_and_status_row(monkeypatch) -> None:
    """A fresh call should create the RunLog + one RunStockStatus row."""
    _seed_stock()
    submitted: list = []
    monkeypatch.setattr(
        ss.refresh_worker,
        "submit",
        lambda factory: submitted.append(factory) or None,
    )

    result = ss.start_single_refresh_background("TEST00000001")
    assert result["status"] == "started"
    assert result["phase"] == "queued"
    assert result["run_id"] is not None

    db = SessionLocal()
    try:
        run = db.get(RunLog, result["run_id"])
        assert run is not None
        assert run.stocks_total == 1
        assert run.phase == "queued"

        rows = (
            db.query(RunStockStatus)
            .filter(RunStockStatus.run_id == run.id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].isin == "TEST00000001"
        assert rows[0].overall_status == "not_started"

        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock is not None and lock.locked is True
    finally:
        db.close()
    assert len(submitted) == 1


def test_start_single_refresh_returns_already_running_when_locked(monkeypatch) -> None:
    """If the shared lock is held by an active run, no new run is created."""
    _seed_stock()
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)

    db = SessionLocal()
    try:
        existing = RunLog(phase="running", started_at=utcnow())
        db.add(existing)
        db.commit()
        existing_id = existing.id
        db.add(
            JobLock(
                name=ss._LOCK_NAME,
                locked=True,
                owner="other-process",
                acquired_at=utcnow(),
                heartbeat_at=utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    result = ss.start_single_refresh_background("TEST00000001")
    assert result["status"] == "already_running"
    assert result["run_id"] == existing_id

    db = SessionLocal()
    try:
        run_count = db.query(RunLog).count()
        assert run_count == 1
    finally:
        db.close()


def test_start_single_refresh_unknown_isin_returns_not_found(monkeypatch) -> None:
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)
    result = ss.start_single_refresh_background("TEST00000404")
    assert result == {"run_id": None, "phase": None, "status": "not_found"}


# ---------------------------------------------------------------------------
# _execute_single_refresh
# ---------------------------------------------------------------------------


def test_execute_single_refresh_marks_steps_done_and_persists_data(monkeypatch) -> None:
    """Happy path: every step ends up `done`, market data is persisted."""
    _seed_stock(isin="TEST00000010", name="Happy Path")
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)
    # The executor lives in the focused `refresh_runner` module after the
    # split; patch the provider binding there so the runner picks it up.
    monkeypatch.setattr(
        ss.refresh_runner,
        "YFinanceProvider",
        lambda: _FakeProvider(
            quote=QuoteData(current_price=99.5, day_change_pct=0.7, currency="USD"),
            metrics=MetricsData(pe_forward=21.0, market_cap=1.2e9),
        ),
    )

    start = ss.start_single_refresh_background("TEST00000010")
    run_id = start["run_id"]
    assert run_id is not None

    asyncio.run(ss._execute_single_refresh(run_id, ss._process_owner(), "TEST00000010"))

    db = SessionLocal()
    try:
        run = db.get(RunLog, run_id)
        assert run is not None
        assert run.phase == "finished"
        assert run.status == "ok"
        assert run.stocks_done == 1
        assert run.stocks_success == 1
        assert run.stocks_error == 0

        row = (
            db.query(RunStockStatus)
            .filter(RunStockStatus.run_id == run_id)
            .one()
        )
        assert row.overall_status == "done"
        assert row.symbol_status == "done"
        assert row.quote_status == "done"
        assert row.metrics_status == "done"
        assert row.resolved_symbol == "FAKE"

        market = db.get(MarketData, "TEST00000010")
        assert market is not None
        assert market.current_price == 99.5
        assert market.last_status == "ok"

        metrics = db.get(Metrics, "TEST00000010")
        assert metrics is not None
        assert metrics.pe_forward == 21.0

        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock is not None and lock.locked is False
    finally:
        db.close()


def test_execute_single_refresh_records_quote_failure(monkeypatch) -> None:
    """A provider failure during the quote step should mark the run as errored."""
    _seed_stock(isin="TEST00000020", name="Quote Failure")
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)
    monkeypatch.setattr(
        ss.refresh_runner,
        "YFinanceProvider",
        lambda: _FakeProvider(quote_error=RuntimeError("yahoo down")),
    )
    # Skip the back-off so the test stays fast.
    monkeypatch.setattr(ss.refresh_runner, "_RETRY_DELAYS", (0,))

    start = ss.start_single_refresh_background("TEST00000020")
    run_id = start["run_id"]
    assert run_id is not None

    asyncio.run(ss._execute_single_refresh(run_id, ss._process_owner(), "TEST00000020"))

    db = SessionLocal()
    try:
        run = db.get(RunLog, run_id)
        assert run is not None
        assert run.phase == "finished"
        assert run.status == "partial_error"
        assert run.stocks_error == 1
        assert run.error_details and "quote" in run.error_details

        row = (
            db.query(RunStockStatus)
            .filter(RunStockStatus.run_id == run_id)
            .one()
        )
        assert row.overall_status == "error"
        assert row.symbol_status == "done"
        assert row.quote_status == "error"
        assert row.metrics_status == "not_started"

        market = db.get(MarketData, "TEST00000020")
        assert market is not None
        assert market.last_status == "error"

        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock is not None and lock.locked is False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Bulk regression
# ---------------------------------------------------------------------------


def test_bulk_refresh_still_uses_market_steps_helper(monkeypatch) -> None:
    """Regression: extracting `_process_market_steps` must not break bulk runs."""
    _seed_stock(isin="TEST00000030", name="Bulk Regression")
    monkeypatch.setattr(ss.refresh_worker, "submit", lambda factory: None)
    monkeypatch.setattr(
        ss.refresh_runner,
        "YFinanceProvider",
        lambda: _FakeProvider(),
    )

    start = ss.start_refresh_all_background()
    run_id = start["run_id"]
    assert run_id is not None

    asyncio.run(ss._execute_refresh(run_id, "test-owner"))

    db = SessionLocal()
    try:
        run = db.get(RunLog, run_id)
        assert run is not None
        assert run.phase == "finished"
        assert run.status == "ok"
        rows = (
            db.query(RunStockStatus)
            .filter(RunStockStatus.run_id == run_id)
            .all()
        )
        # Find our test row among any other seeded stocks.
        ours = [r for r in rows if r.isin == "TEST00000030"]
        assert len(ours) == 1
        assert ours[0].overall_status == "done"
        assert ours[0].metrics_status == "done"
    finally:
        db.close()
