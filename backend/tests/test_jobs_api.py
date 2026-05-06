"""HTTP-level tests for the job-source CRUD + trend + bulk endpoints."""
from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.job_source import JobSnapshot, JobSource, RunJobStatus
from app.models.run_log import JobLock, RunLog


def _login(client: TestClient, *, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


@pytest.fixture(autouse=True)
def _reset_jobs_state(monkeypatch):
    """Wipe job-related rows + suppress real background work for each test."""
    db = SessionLocal()
    try:
        db.query(JobSnapshot).delete()
        db.query(RunJobStatus).delete()
        db.query(JobSource).delete()
        db.query(JobLock).delete()
        db.query(RunLog).delete()
        db.commit()
    finally:
        db.close()

    # Avoid kicking off the real RefreshWorker thread from request handlers.
    from app.services import jobs_service

    monkeypatch.setattr(
        jobs_service.refresh_worker, "submit", lambda *_args, **_kw: None
    )

    yield


@pytest.fixture
def patch_httpx(monkeypatch):
    def _set(handler):
        transport = httpx.MockTransport(handler)
        original = httpx.AsyncClient

        def _factory(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", _factory)

    return _set


def _create_source_payload(**overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "name": "Acme Careers",
        "portal_url": "https://acme.example.com/careers",
        "adapter_type": "json_get_path_int",
        "adapter_settings": {
            "endpoint": "https://api.example.com/jobs",
            "value_path": "total",
        },
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_then_list_then_get():
    client = TestClient(app)
    csrf = _login(client)

    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    assert create.status_code == 200
    body = create.json()
    assert body["id"]
    assert body["name"] == "Acme Careers"
    assert body["latest_count"] is None
    sid = body["id"]

    listing = client.get("/api/v1/job-sources").json()
    assert any(s["id"] == sid for s in listing)

    detail = client.get(f"/api/v1/job-sources/{sid}").json()
    assert detail["name"] == "Acme Careers"
    assert detail["adapter_type"] == "json_get_path_int"


def test_invalid_adapter_type_rejected():
    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(adapter_type="ouija_board"),
    )
    assert resp.status_code == 422


def test_invalid_url_rejected():
    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(portal_url="acme.example.com"),
    )
    assert resp.status_code == 422


def test_patch_updates_fields():
    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    patch = client.patch(
        f"/api/v1/job-sources/{sid}",
        headers={"X-CSRF-Token": csrf},
        json={"is_active": False, "name": "Renamed"},
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["is_active"] is False
    assert body["name"] == "Renamed"


def test_delete_removes_source():
    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    resp = client.delete(
        f"/api/v1/job-sources/{sid}", headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 200
    missing = client.get(f"/api/v1/job-sources/{sid}")
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Test endpoint (live adapter dry run)
# ---------------------------------------------------------------------------


def test_test_endpoint_returns_count(patch_httpx):
    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    patch_httpx(lambda req: httpx.Response(200, json={"total": 99}))
    resp = client.post(
        f"/api/v1/job-sources/{sid}/test", headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["jobs_count"] == 99


def test_test_endpoint_reports_error_for_bad_response(patch_httpx):
    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    patch_httpx(lambda req: httpx.Response(500, text="bang"))
    resp = client.post(
        f"/api/v1/job-sources/{sid}/test", headers={"X-CSRF-Token": csrf}
    )
    body = resp.json()
    assert body["status"] == "error"
    assert body["error"]


# ---------------------------------------------------------------------------
# Trend endpoint
# ---------------------------------------------------------------------------


def test_trend_returns_chronological_points():
    """Insert 3 manual snapshots and verify the API returns them sorted."""
    from datetime import date, timedelta

    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        for i, count in enumerate([100, 110, 105]):
            db.add(
                JobSnapshot(
                    job_source_id=sid,
                    snapshot_date=today - timedelta(days=2 - i),
                    jobs_count=count,
                    raw_meta={},
                )
            )
        db.commit()
    finally:
        db.close()

    trend = client.get(f"/api/v1/job-sources/{sid}/trend?days=30").json()
    assert len(trend["points"]) == 3
    counts = [p["jobs_count"] for p in trend["points"]]
    assert counts == [100, 110, 105]


def test_list_includes_latest_count_and_delta():
    """After inserting two snapshots, the list endpoint surfaces delta_7d."""
    from datetime import date, timedelta

    client = TestClient(app)
    csrf = _login(client)
    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )
    sid = create.json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        db.add(
            JobSnapshot(
                job_source_id=sid,
                snapshot_date=today - timedelta(days=7),
                jobs_count=80,
                raw_meta={},
            )
        )
        db.add(
            JobSnapshot(
                job_source_id=sid,
                snapshot_date=today,
                jobs_count=100,
                raw_meta={},
            )
        )
        db.commit()
    finally:
        db.close()

    listing = client.get("/api/v1/job-sources").json()
    row = next(s for s in listing if s["id"] == sid)
    assert row["latest_count"] == 100
    assert row["delta_7d"] == 20


# ---------------------------------------------------------------------------
# Bulk refresh endpoints
# ---------------------------------------------------------------------------


def test_bulk_refresh_creates_jobs_run():
    client = TestClient(app)
    csrf = _login(client)
    client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(),
    )

    resp = client.post(
        "/api/v1/jobs-runs/refresh-all", headers={"X-CSRF-Token": csrf}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("started", "skipped", "already_running")
    if body["status"] == "started":
        run_id = body["run_id"]
        db = SessionLocal()
        try:
            run = db.get(RunLog, run_id)
            assert run.run_type == "jobs"
        finally:
            db.close()


# ---------------------------------------------------------------------------
# /stocks/{isin}/jobs aggregation
# ---------------------------------------------------------------------------


def test_stock_jobs_aggregation():
    """Two sources for the same ISIN aggregate latest counts on the stock view."""
    from datetime import date

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        # Use a unique ISIN that does not collide with the seed.
        stock = Stock(isin="DE0008888888", name="Test AG")
        db.add(stock)
        db.commit()
    finally:
        db.close()

    create_a = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Test AG (Karriere DE)", isin="DE0008888888"),
    )
    create_b = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Test AG (Karriere INT)", isin="DE0008888888"),
    )
    sid_a = create_a.json()["id"]
    sid_b = create_b.json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        db.add(
            JobSnapshot(
                job_source_id=sid_a,
                snapshot_date=today,
                jobs_count=30,
                raw_meta={},
            )
        )
        db.add(
            JobSnapshot(
                job_source_id=sid_b,
                snapshot_date=today,
                jobs_count=12,
                raw_meta={},
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/stocks/DE0008888888/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["isin"] == "DE0008888888"
    assert len(body["sources"]) == 2
    assert body["total_latest"] == 42

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0008888888")
        if stock is not None:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_aggregate_trends_sums_per_isin_and_day():
    """Two sources for the same ISIN: per-day counts must be summed.

    Also verifies that sources without an ISIN (e.g. private companies the
    admin tracks but that are not on the watchlist) are excluded from the
    aggregate response — they have no row to attach to anyway.
    """
    from datetime import date, timedelta

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0007777777", name="Trend AG"))
        db.commit()
    finally:
        db.close()

    create_a = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Trend AG (DE)", isin="DE0007777777"),
    )
    create_b = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Trend AG (INT)", isin="DE0007777777"),
    )
    create_c = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="No-ISIN portal", isin=None),
    )
    sid_a = create_a.json()["id"]
    sid_b = create_b.json()["id"]
    sid_c = create_c.json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        yesterday = today - timedelta(days=1)
        # Day 1: A=10, B=5  -> total 15
        db.add(JobSnapshot(job_source_id=sid_a, snapshot_date=yesterday, jobs_count=10, raw_meta={}))
        db.add(JobSnapshot(job_source_id=sid_b, snapshot_date=yesterday, jobs_count=5, raw_meta={}))
        # Day 2: A=12, B=8  -> total 20
        db.add(JobSnapshot(job_source_id=sid_a, snapshot_date=today, jobs_count=12, raw_meta={}))
        db.add(JobSnapshot(job_source_id=sid_b, snapshot_date=today, jobs_count=8, raw_meta={}))
        # ISIN-less source — must be ignored.
        db.add(JobSnapshot(job_source_id=sid_c, snapshot_date=today, jobs_count=99, raw_meta={}))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/job-sources/trends?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 30
    items_by_isin = {item["isin"]: item["points"] for item in body["items"]}
    assert "DE0007777777" in items_by_isin
    # Sources without an ISIN must not surface as their own bucket.
    assert all(item["isin"] is not None for item in body["items"])

    points = items_by_isin["DE0007777777"]
    assert len(points) == 2
    counts = {p["snapshot_date"]: p["jobs_count"] for p in points}
    assert counts[yesterday.isoformat()] == 15
    assert counts[today.isoformat()] == 20

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0007777777")
        if stock is not None:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_aggregate_trends_excludes_inactive_sources():
    """Inactive sources are dormant and must not show up in the sparkline."""
    from datetime import date

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0006666666", name="Inactive AG"))
        db.commit()
    finally:
        db.close()

    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(
            name="Inactive AG portal", isin="DE0006666666", is_active=False
        ),
    )
    sid = create.json()["id"]

    db = SessionLocal()
    try:
        db.add(
            JobSnapshot(
                job_source_id=sid,
                snapshot_date=date.today(),
                jobs_count=42,
                raw_meta={},
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/job-sources/trends?days=30").json()
    items_by_isin = {item["isin"]: item["points"] for item in resp["items"]}
    assert "DE0006666666" not in items_by_isin

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0006666666")
        if stock is not None:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# /stocks/{isin}/jobs/trend
# ---------------------------------------------------------------------------


def test_stock_jobs_trend_empty_when_no_sources():
    """A stock with no job sources returns an empty points list (not 404)."""
    from app.models.stock import Stock

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0005550000", name="Empty AG"))
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/stocks/DE0005550000/jobs/trend?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert body["isin"] == "DE0005550000"
    assert body["days"] == 30
    assert body["points"] == []

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0005550000")
        if stock:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_stock_jobs_trend_single_source():
    """Snapshots from a single source appear sorted chronologically."""
    from datetime import date, timedelta

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0004440000", name="Single AG"))
        db.commit()
    finally:
        db.close()

    create = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Single AG portal", isin="DE0004440000"),
    )
    sid = create.json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        for i, count in enumerate([50, 55, 60]):
            db.add(
                JobSnapshot(
                    job_source_id=sid,
                    snapshot_date=today - timedelta(days=2 - i),
                    jobs_count=count,
                    raw_meta={},
                )
            )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/stocks/DE0004440000/jobs/trend?days=30")
    assert resp.status_code == 200
    body = resp.json()
    counts = [p["jobs_count"] for p in body["points"]]
    assert counts == [50, 55, 60]

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0004440000")
        if stock:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_stock_jobs_trend_multiple_sources_summed():
    """Two active sources are summed per day."""
    from datetime import date

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0003330000", name="Multi AG"))
        db.commit()
    finally:
        db.close()

    sid_a = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Multi AG (DE)", isin="DE0003330000"),
    ).json()["id"]
    sid_b = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Multi AG (INT)", isin="DE0003330000"),
    ).json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        db.add(JobSnapshot(job_source_id=sid_a, snapshot_date=today, jobs_count=40, raw_meta={}))
        db.add(JobSnapshot(job_source_id=sid_b, snapshot_date=today, jobs_count=25, raw_meta={}))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/stocks/DE0003330000/jobs/trend?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 1
    assert body["points"][0]["jobs_count"] == 65

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0003330000")
        if stock:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_stock_jobs_trend_excludes_inactive_sources():
    """Inactive sources are not counted in the aggregate trend."""
    from datetime import date

    from app.models.stock import Stock

    client = TestClient(app)
    csrf = _login(client)

    db = SessionLocal()
    try:
        db.add(Stock(isin="DE0002220000", name="Inactive Trend AG"))
        db.commit()
    finally:
        db.close()

    active_sid = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Active portal", isin="DE0002220000", is_active=True),
    ).json()["id"]
    inactive_sid = client.post(
        "/api/v1/job-sources",
        headers={"X-CSRF-Token": csrf},
        json=_create_source_payload(name="Inactive portal", isin="DE0002220000", is_active=False),
    ).json()["id"]

    db = SessionLocal()
    try:
        today = date.today()
        db.add(JobSnapshot(job_source_id=active_sid, snapshot_date=today, jobs_count=30, raw_meta={}))
        db.add(JobSnapshot(job_source_id=inactive_sid, snapshot_date=today, jobs_count=999, raw_meta={}))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/v1/stocks/DE0002220000/jobs/trend?days=30")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["points"]) == 1
    assert body["points"][0]["jobs_count"] == 30  # inactive (999) excluded

    db = SessionLocal()
    try:
        stock = db.get(Stock, "DE0002220000")
        if stock:
            db.delete(stock)
            db.commit()
    finally:
        db.close()


def test_stock_jobs_trend_404_for_unknown_isin():
    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/stocks/XX9999999999/jobs/trend?days=30")
    assert resp.status_code == 404


def test_run_logs_filtered_by_run_type():
    """`?run_type=jobs` excludes market-data runs and vice versa."""
    from app.models.run_log import RunLog
    from app.core.time import utcnow

    db = SessionLocal()
    try:
        db.add(RunLog(run_type="market", phase="finished", started_at=utcnow(), status="ok"))
        db.add(RunLog(run_type="jobs", phase="finished", started_at=utcnow(), status="ok"))
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    _login(client)

    market_only = client.get("/api/v1/run-logs?run_type=market").json()
    jobs_only = client.get("/api/v1/run-logs?run_type=jobs").json()

    assert all(r["run_type"] == "market" for r in market_only)
    assert all(r["run_type"] == "jobs" for r in jobs_only)
    assert len(market_only) >= 1
    assert len(jobs_only) >= 1
