"""Tests for the JobLock TTL/heartbeat semantics in scheduler_service."""
from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.run_log import JobLock, RunLog
from app.services import jobs_service, lock_manager, scheduler_service as ss


@pytest.fixture(autouse=True)
def _reset_lock():
    """Make sure every test starts with a clean lock row."""
    db = SessionLocal()
    try:
        db.query(JobLock).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(JobLock).delete()
        db.commit()
    finally:
        db.close()


def _set_lock(**fields) -> None:
    db = SessionLocal()
    try:
        lock = db.get(JobLock, ss._LOCK_NAME) or JobLock(name=ss._LOCK_NAME)
        for key, value in fields.items():
            setattr(lock, key, value)
        db.add(lock)
        db.commit()
    finally:
        db.close()


def test_is_lock_stale_when_unlocked() -> None:
    lock = JobLock(name="x", locked=False, heartbeat_at=utcnow())
    assert ss._is_lock_stale(lock) is False


def test_is_lock_stale_without_heartbeat() -> None:
    """Old rows without heartbeat data are always treated as stale."""
    lock = JobLock(name="x", locked=True, heartbeat_at=None)
    assert ss._is_lock_stale(lock) is True


def test_is_lock_stale_when_heartbeat_too_old() -> None:
    too_old = utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(seconds=10)
    lock = JobLock(name="x", locked=True, heartbeat_at=too_old)
    assert ss._is_lock_stale(lock) is True


def test_is_lock_stale_when_heartbeat_fresh() -> None:
    lock = JobLock(name="x", locked=True, heartbeat_at=utcnow())
    assert ss._is_lock_stale(lock) is False


def test_heartbeat_only_renews_for_owner() -> None:
    _set_lock(
        locked=True,
        owner="owner-a",
        acquired_at=utcnow() - timedelta(minutes=1),
        heartbeat_at=utcnow() - timedelta(minutes=1),
    )

    db = SessionLocal()
    try:
        before = db.get(JobLock, ss._LOCK_NAME).heartbeat_at
        ss._heartbeat(db, "stranger")
        db.expire_all()
        unchanged = db.get(JobLock, ss._LOCK_NAME).heartbeat_at
        assert unchanged == before

        ss._heartbeat(db, "owner-a")
        db.expire_all()
        renewed = db.get(JobLock, ss._LOCK_NAME).heartbeat_at
        assert renewed > before
    finally:
        db.close()


def test_recover_stale_locks_resets_lock_and_marks_runs() -> None:
    too_old = utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(minutes=1)
    _set_lock(locked=True, owner="dead", acquired_at=too_old, heartbeat_at=too_old)

    db = SessionLocal()
    try:
        run = RunLog(phase="running", started_at=utcnow())
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    ss.recover_stale_locks()

    db = SessionLocal()
    try:
        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock is not None
        assert lock.locked is False
        assert lock.owner is None

        recovered = db.get(RunLog, run_id)
        assert recovered.phase == "finished"
        assert recovered.status == "error"
        assert recovered.finished_at is not None
        assert "recovered after crash" in (recovered.error_details or "")
    finally:
        db.close()


def test_recover_stale_locks_keeps_fresh_lock() -> None:
    _set_lock(
        locked=True,
        owner="alive",
        acquired_at=utcnow(),
        heartbeat_at=utcnow(),
    )
    ss.recover_stale_locks()

    db = SessionLocal()
    try:
        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock.locked is True
        assert lock.owner == "alive"
    finally:
        db.close()


def test_try_acquire_lock_serializes_concurrent_callers() -> None:
    """Two threads racing on the same lock: exactly one should acquire it."""
    barrier = threading.Barrier(2)
    results: list[bool] = []
    results_lock = threading.Lock()

    def attempt(owner_id: str) -> None:
        db = SessionLocal()
        try:
            barrier.wait(timeout=2)
            ok = lock_manager.try_acquire_lock(db, ss._LOCK_NAME, owner_id)
            with results_lock:
                results.append(ok)
        finally:
            db.close()

    threads = [
        threading.Thread(target=attempt, args=(f"owner-{i}",)) for i in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert results.count(True) == 1
    assert results.count(False) == 1


def test_try_acquire_lock_steals_stale_lock() -> None:
    """A heartbeat older than the TTL is treated as a crashed owner."""
    too_old = utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(minutes=1)
    _set_lock(
        locked=True,
        owner="dead-owner",
        acquired_at=too_old,
        heartbeat_at=too_old,
    )

    db = SessionLocal()
    try:
        assert lock_manager.try_acquire_lock(db, ss._LOCK_NAME, "fresh") is True
        lock = db.get(JobLock, ss._LOCK_NAME)
        db.expire(lock)
        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock.owner == "fresh"
    finally:
        db.close()


def test_release_lock_only_for_owner() -> None:
    db = SessionLocal()
    try:
        assert lock_manager.try_acquire_lock(db, ss._LOCK_NAME, "owner-a") is True
        # Foreign owner must not be able to release.
        assert lock_manager.release_lock(db, ss._LOCK_NAME, "intruder") is False
        # The rightful owner releases successfully.
        assert lock_manager.release_lock(db, ss._LOCK_NAME, "owner-a") is True
        lock = db.get(JobLock, ss._LOCK_NAME)
        db.expire(lock)
        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock.locked is False
        assert lock.owner is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Run-type-aware stale-lock recovery (a4 / a5)
# ---------------------------------------------------------------------------


def _make_stale_lock(lock_name: str) -> None:
    too_old = utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(minutes=1)
    db = SessionLocal()
    try:
        lock = db.get(JobLock, lock_name) or JobLock(name=lock_name)
        lock.locked = True
        lock.owner = "dead"
        lock.acquired_at = too_old
        lock.heartbeat_at = too_old
        db.add(lock)
        db.commit()
    finally:
        db.close()


def test_recover_stale_locks_only_finalizes_matching_run_type():
    """Market recovery must not flip a jobs RunLog to error.

    Creates a stale ``daily_refresh`` lock plus a healthy-looking jobs run
    (run_type='jobs', phase='running').  After calling
    ``refresh_lock.recover_stale_locks()`` (which passes run_type='market')
    the market lock is released but the jobs run remains untouched.
    """
    _make_stale_lock(ss._LOCK_NAME)

    db = SessionLocal()
    try:
        jobs_run = RunLog(run_type="jobs", phase="running", started_at=utcnow())
        db.add(jobs_run)
        db.commit()
        jobs_run_id = jobs_run.id
    finally:
        db.close()

    ss.recover_stale_locks()

    db = SessionLocal()
    try:
        market_lock = db.get(JobLock, ss._LOCK_NAME)
        assert market_lock is not None
        assert market_lock.locked is False, "market lock should have been released"

        recovered = db.get(RunLog, jobs_run_id)
        assert recovered is not None
        assert recovered.phase == "running", (
            "jobs RunLog must NOT be finalised by market recovery"
        )
    finally:
        db.close()


def test_recover_stale_jobs_lock_resets_only_jobs_runs():
    """Jobs recovery must not flip a market RunLog to error.

    Creates a stale ``daily_jobs_refresh`` lock plus a stuck market run
    (run_type=None, phase='running').  After calling
    ``jobs_service.recover_stale_jobs_locks()`` only the jobs lock is
    released; the market run stays in phase='running'.
    """
    _make_stale_lock(jobs_service._JOBS_LOCK_NAME)

    db = SessionLocal()
    try:
        # Legacy market run with run_type=None (pre-0002 schema).
        market_run = RunLog(phase="running", started_at=utcnow())
        db.add(market_run)
        db.commit()
        market_run_id = market_run.id
    finally:
        db.close()

    jobs_service.recover_stale_jobs_locks()

    db = SessionLocal()
    try:
        jobs_lock = db.get(JobLock, jobs_service._JOBS_LOCK_NAME)
        assert jobs_lock is not None
        assert jobs_lock.locked is False, "jobs lock should have been released"

        recovered = db.get(RunLog, market_run_id)
        assert recovered is not None
        assert recovered.phase == "running", (
            "market RunLog must NOT be finalised by jobs recovery"
        )
    finally:
        db.close()
