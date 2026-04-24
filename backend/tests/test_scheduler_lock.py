"""Tests for the JobLock TTL/heartbeat semantics in scheduler_service."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.session import SessionLocal
from app.models.run_log import JobLock, RunLog
from app.services import scheduler_service as ss


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
    lock = JobLock(name="x", locked=False, heartbeat_at=datetime.utcnow())
    assert ss._is_lock_stale(lock) is False


def test_is_lock_stale_without_heartbeat() -> None:
    """Old rows without heartbeat data are always treated as stale."""
    lock = JobLock(name="x", locked=True, heartbeat_at=None)
    assert ss._is_lock_stale(lock) is True


def test_is_lock_stale_when_heartbeat_too_old() -> None:
    too_old = datetime.utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(seconds=10)
    lock = JobLock(name="x", locked=True, heartbeat_at=too_old)
    assert ss._is_lock_stale(lock) is True


def test_is_lock_stale_when_heartbeat_fresh() -> None:
    lock = JobLock(name="x", locked=True, heartbeat_at=datetime.utcnow())
    assert ss._is_lock_stale(lock) is False


def test_heartbeat_only_renews_for_owner() -> None:
    _set_lock(
        locked=True,
        owner="owner-a",
        acquired_at=datetime.utcnow() - timedelta(minutes=1),
        heartbeat_at=datetime.utcnow() - timedelta(minutes=1),
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
    too_old = datetime.utcnow() - ss._LOCK_HEARTBEAT_TTL - timedelta(minutes=1)
    _set_lock(locked=True, owner="dead", acquired_at=too_old, heartbeat_at=too_old)

    db = SessionLocal()
    try:
        run = RunLog(phase="running", started_at=datetime.utcnow())
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
        acquired_at=datetime.utcnow(),
        heartbeat_at=datetime.utcnow(),
    )
    ss.recover_stale_locks()

    db = SessionLocal()
    try:
        lock = db.get(JobLock, ss._LOCK_NAME)
        assert lock.locked is True
        assert lock.owner == "alive"
    finally:
        db.close()
