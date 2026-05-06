"""Tests for the job-scrape pipeline (jobs_service).

Covers:
* `start_refresh_jobs_background` happy path + already-running guard.
* Successful pipeline run produces a snapshot + done status.
* Adapter errors mark the source as `error` and do not produce a snapshot.
* Cancel registry honoured between sources.
* Idempotent UPSERT on `(job_source_id, snapshot_date)`.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.job_source import JobSnapshot, JobSource, RunJobStatus
from app.models.run_log import JobLock, RunLog
from app.models.settings import AppSettings
from app.services import jobs_service


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    """Reset everything jobs-pipeline-related between tests.

    Also stubs out ``refresh_worker.submit`` so calls to the public
    ``start_*`` entrypoints do not spawn real background work that could
    race with the next test's setup. Tests that want to exercise
    ``_execute_jobs_refresh`` invoke it directly via ``asyncio.run``.
    """
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
    with jobs_service._jobs_cancel_lock:
        jobs_service._cancelled_jobs_run_ids.clear()

    monkeypatch.setattr(
        jobs_service.refresh_worker, "submit", lambda *_args, **_kw: None
    )

    yield

    with jobs_service._jobs_cancel_lock:
        jobs_service._cancelled_jobs_run_ids.clear()


def _make_source(
    *,
    name: str = "Test",
    adapter_type: str = "json_get_path_int",
    settings: dict[str, Any] | None = None,
    is_active: bool = True,
) -> int:
    db = SessionLocal()
    try:
        source = JobSource(
            name=name,
            portal_url="https://example.com",
            adapter_type=adapter_type,
            adapter_settings=settings
            or {"endpoint": "https://api.example.com/jobs", "value_path": "total"},
            is_active=is_active,
        )
        db.add(source)
        db.commit()
        return source.id
    finally:
        db.close()


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


# ---------------------------------------------------------------------------
# start_refresh_jobs_background
# ---------------------------------------------------------------------------


def test_skipped_when_jobs_disabled():
    db = SessionLocal()
    try:
        cfg = db.get(AppSettings, 1) or AppSettings(id=1)
        cfg.jobs_enabled = False
        db.add(cfg)
        db.commit()
    finally:
        db.close()

    result = jobs_service.start_refresh_jobs_background(manual=False)
    assert result["status"] == "skipped"

    db = SessionLocal()
    try:
        cfg = db.get(AppSettings, 1)
        cfg.jobs_enabled = True
        db.add(cfg)
        db.commit()
    finally:
        db.close()


def test_manual_bypasses_disabled_toggle():
    db = SessionLocal()
    try:
        cfg = db.get(AppSettings, 1) or AppSettings(id=1)
        cfg.jobs_enabled = False
        db.add(cfg)
        db.commit()
    finally:
        db.close()

    _make_source()
    result = jobs_service.start_refresh_jobs_background(manual=True)
    assert result["status"] == "started"
    assert result["run_id"] is not None

    db = SessionLocal()
    try:
        cfg = db.get(AppSettings, 1)
        cfg.jobs_enabled = True
        db.add(cfg)
        db.commit()
    finally:
        db.close()


def test_already_running_guard():
    """Second call while the lock is held returns ``already_running``."""
    db = SessionLocal()
    try:
        # Force lock to look held by another owner.
        from app.services import lock_manager

        lock_manager.try_acquire_lock(db, jobs_service._JOBS_LOCK_NAME, "other-owner")
    finally:
        db.close()

    result = jobs_service.start_refresh_jobs_background(manual=True)
    assert result["status"] == "already_running"


def test_creates_run_with_jobs_run_type():
    _make_source()
    result = jobs_service.start_refresh_jobs_background(manual=True)
    run_id = result["run_id"]
    assert run_id is not None

    db = SessionLocal()
    try:
        run = db.get(RunLog, run_id)
        assert run.run_type == "jobs"
        assert run.stocks_total == 1
        assert run.phase == "queued"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# _execute_jobs_refresh
# ---------------------------------------------------------------------------


def _bootstrap_run_with_sources(sources: list[int]) -> tuple[int, str]:
    """Return (run_id, owner) ready for direct ``_execute_jobs_refresh`` call.

    Replicates what ``start_refresh_jobs_background`` does *minus* the
    worker.submit call so the test can run the executor synchronously.
    """
    from app.services import lock_manager
    from app.services.refresh_lock import process_owner

    db = SessionLocal()
    try:
        owner = process_owner()
        assert lock_manager.try_acquire_lock(db, jobs_service._JOBS_LOCK_NAME, owner)
        run = RunLog(run_type="jobs", phase="queued", started_at=utcnow())
        db.add(run)
        db.commit()
        run.stocks_total = len(sources)
        db.add(run)
        for sid in sources:
            db.add(
                RunJobStatus(
                    run_id=run.id,
                    job_source_id=sid,
                )
            )
        db.commit()
        return run.id, owner
    finally:
        db.close()


def test_successful_run_creates_snapshot_and_marks_done(monkeypatch):
    sid = _make_source()
    _patch_httpx(monkeypatch, lambda req: httpx.Response(200, json={"total": 42}))
    run_id, owner = _bootstrap_run_with_sources([sid])

    asyncio.run(jobs_service._execute_jobs_refresh(run_id, owner))

    db = SessionLocal()
    try:
        snaps = db.query(JobSnapshot).all()
        assert len(snaps) == 1
        assert snaps[0].jobs_count == 42
        assert snaps[0].run_id == run_id

        status = (
            db.query(RunJobStatus)
            .filter(RunJobStatus.run_id == run_id, RunJobStatus.job_source_id == sid)
            .one()
        )
        assert status.overall_status == "done"
        assert status.jobs_count == 42

        run = db.get(RunLog, run_id)
        assert run.phase == "finished"
        assert run.status == "ok"
        assert run.stocks_success == 1
        assert run.stocks_error == 0
    finally:
        db.close()


def test_adapter_error_marks_source_failed_no_snapshot(monkeypatch):
    sid = _make_source()
    _patch_httpx(
        monkeypatch, lambda req: httpx.Response(500, json={"detail": "boom"})
    )
    run_id, owner = _bootstrap_run_with_sources([sid])

    asyncio.run(jobs_service._execute_jobs_refresh(run_id, owner))

    db = SessionLocal()
    try:
        # No snapshot persisted on failure.
        assert db.query(JobSnapshot).count() == 0

        status = (
            db.query(RunJobStatus)
            .filter(RunJobStatus.run_id == run_id, RunJobStatus.job_source_id == sid)
            .one()
        )
        assert status.overall_status == "error"
        assert status.error is not None

        run = db.get(RunLog, run_id)
        assert run.phase == "finished"
        assert run.status == "partial_error"
        assert run.stocks_error == 1
        assert run.stocks_success == 0
    finally:
        db.close()


def test_idempotent_snapshot_upsert_on_same_day(monkeypatch):
    """Re-running on the same date overwrites instead of duplicating."""
    sid = _make_source()
    counts = iter([10, 20])
    _patch_httpx(
        monkeypatch,
        lambda req: httpx.Response(200, json={"total": next(counts)}),
    )

    run_id1, owner1 = _bootstrap_run_with_sources([sid])
    asyncio.run(jobs_service._execute_jobs_refresh(run_id1, owner1))

    run_id2, owner2 = _bootstrap_run_with_sources([sid])
    asyncio.run(jobs_service._execute_jobs_refresh(run_id2, owner2))

    db = SessionLocal()
    try:
        snaps = db.query(JobSnapshot).all()
        # UPSERT on (source_id, date) keeps a single row, updated to the
        # latest count.
        assert len(snaps) == 1
        assert snaps[0].jobs_count == 20
        assert snaps[0].run_id == run_id2
    finally:
        db.close()


def test_cancel_skips_remaining_sources(monkeypatch):
    sid_a = _make_source(name="A")
    sid_b = _make_source(name="B")
    _patch_httpx(monkeypatch, lambda req: httpx.Response(200, json={"total": 5}))

    run_id, owner = _bootstrap_run_with_sources([sid_a, sid_b])
    # Pre-flag the run as cancelled. The first source still gets processed
    # (the cancel check fires *between* sources), but the second is skipped.
    jobs_service.request_cancel_for_jobs_run(run_id)

    asyncio.run(jobs_service._execute_jobs_refresh(run_id, owner))

    db = SessionLocal()
    try:
        run = db.get(RunLog, run_id)
        assert run.status == "cancelled"

        # The remaining-cancelled sweep flips not_started rows to cancelled.
        cancelled = (
            db.query(RunJobStatus)
            .filter(
                RunJobStatus.run_id == run_id,
                RunJobStatus.overall_status == "cancelled",
            )
            .count()
        )
        assert cancelled >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# test_source_scrape (admin "Test" button)
# ---------------------------------------------------------------------------


def test_test_source_scrape_returns_count(monkeypatch):
    sid = _make_source()
    _patch_httpx(monkeypatch, lambda req: httpx.Response(200, json={"total": 7}))

    db = SessionLocal()
    try:
        source = db.get(JobSource, sid)
        result = asyncio.run(jobs_service.test_source_scrape(source))
    finally:
        db.close()

    assert result["status"] == "ok"
    assert result["jobs_count"] == 7


def test_test_source_scrape_returns_error_on_failure(monkeypatch):
    sid = _make_source()
    _patch_httpx(monkeypatch, lambda req: httpx.Response(500, text="bang"))

    db = SessionLocal()
    try:
        source = db.get(JobSource, sid)
        result = asyncio.run(jobs_service.test_source_scrape(source))
    finally:
        db.close()

    assert result["status"] == "error"
    assert "error" in result


# ---------------------------------------------------------------------------
# Playwright extra not installed: make sure the error mentions the install
# command so an operator sees how to fix it. We swap the registry instead of
# uninstalling the real package — that way the test runs identically on a
# backend with or without the optional extra.
# ---------------------------------------------------------------------------


def test_playwright_adapter_missing_extra_returns_clear_error(monkeypatch):
    """If the Playwright extra is not installed, the adapter is missing
    from the registry. The error must point at the install command so
    an operator does not have to grep the codebase to figure out how
    to fix it.
    """
    sid = _make_source(adapter_type="playwright_text_regex", settings={})

    # Swap in a fresh dict that omits every Playwright adapter so we
    # test the missing-extra branch without polluting global state.
    # `monkeypatch.setattr` on the module attribute restores it on
    # teardown.
    from app.providers import jobs as jobs_pkg

    fake_registry = {
        k: v
        for k, v in jobs_pkg.ADAPTER_REGISTRY.items()
        if k not in jobs_pkg.PLAYWRIGHT_ADAPTER_NAMES
    }
    monkeypatch.setattr(jobs_pkg, "ADAPTER_REGISTRY", fake_registry)
    # ``jobs_service`` imported the symbol by name, so we need to patch
    # the alias the service uses, not just the package attribute.
    monkeypatch.setattr(jobs_service, "ADAPTER_REGISTRY", fake_registry)

    db = SessionLocal()
    try:
        source = db.get(JobSource, sid)
        result = asyncio.run(jobs_service.test_source_scrape(source))
    finally:
        db.close()

    assert result["status"] == "error"
    assert "playwright" in result["error"].lower()
    assert "pip install" in result["error"]
