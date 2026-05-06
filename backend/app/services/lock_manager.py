"""Atomic job-lock primitives shared by the refresh pipeline.

The previous implementation read the lock row, checked `locked` in Python
and then wrote the new state in a separate statement. Two concurrent
acquire attempts could both observe `locked=False` before either commits,
leaving us with overlapping refresh runs.

This module replaces that read-modify-write with a single conditional
`UPDATE` so the database — SQLite via its writer lock, Postgres via row
locks — is the only arbiter. The rowcount of the UPDATE tells us whether
we won the race.
"""
from __future__ import annotations

import logging
import os
import socket
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.session import SessionLocal, engine
from app.models.run_log import JobLock, RunLog

logger = logging.getLogger(__name__)


# Public default TTL. A heartbeat older than this is treated as a crashed
# owner whose lock may be stolen by the next acquire attempt.
LOCK_HEARTBEAT_TTL = timedelta(minutes=5)


def process_owner() -> str:
    """Stable identifier for the current process / host combo."""
    return f"{socket.gethostname()}:{os.getpid()}"


def is_lock_stale(lock: JobLock, ttl: timedelta = LOCK_HEARTBEAT_TTL) -> bool:
    if not lock.locked:
        return False
    if lock.heartbeat_at is None:
        # Pre-TTL row: treat as stale so a fresh process can take over.
        return True
    return utcnow() - lock.heartbeat_at > ttl


def _ensure_lock_row(db: Session, name: str) -> None:
    """Make sure a row with the given name exists.

    Uses an INSERT-OR-IGNORE / ON CONFLICT DO NOTHING so two concurrent
    callers can race here without one of them blowing up on the PK
    constraint. The SQL dialect is detected at runtime so the same code
    works against SQLite (today) and Postgres (future).
    """
    if db.get(JobLock, name) is not None:
        return

    dialect = engine.dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = sqlite_insert(JobLock).values(name=name, locked=False)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        db.execute(stmt)
    elif dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(JobLock).values(name=name, locked=False)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        db.execute(stmt)
    else:
        # Generic fallback: best-effort INSERT, swallow IntegrityError if a
        # parallel process beat us to it. We rollback the failed flush so
        # the session stays usable for the subsequent UPDATE.
        try:
            db.add(JobLock(name=name, locked=False))
            db.flush()
        except Exception:
            db.rollback()
    db.commit()


def try_acquire_lock(
    db: Session,
    name: str,
    owner: str,
    *,
    ttl: timedelta = LOCK_HEARTBEAT_TTL,
) -> bool:
    """Atomically claim the named lock. Returns True iff `owner` now holds it.

    Issues a single conditional `UPDATE` that succeeds when the row is
    either unlocked or its heartbeat is older than `ttl` (stale owner).
    The DB serialises concurrent updates so exactly one caller observes
    `rowcount == 1`.
    """
    _ensure_lock_row(db, name)
    now = utcnow()
    stale_cutoff = now - ttl
    stmt = (
        update(JobLock)
        .where(JobLock.name == name)
        .where(
            (JobLock.locked.is_(False))
            | (JobLock.heartbeat_at.is_(None))
            | (JobLock.heartbeat_at < stale_cutoff)
        )
        .values(locked=True, owner=owner, acquired_at=now, heartbeat_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1


def release_lock(db: Session, name: str, owner: str) -> bool:
    """Drop the lock if (and only if) `owner` still holds it."""
    stmt = (
        update(JobLock)
        .where(JobLock.name == name, JobLock.owner == owner)
        .values(locked=False, owner=None, heartbeat_at=None)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount == 1


def heartbeat_lock(
    db: Session, name: str, owner: str, *, commit: bool = True
) -> bool:
    """Renew the lock's heartbeat. No-op when the caller is not the owner.

    Pass `commit=False` to coalesce the heartbeat into a surrounding
    transaction (e.g. the per-stock counter update in the refresh loop) and
    save one round-trip / fsync per stock.
    """
    stmt = (
        update(JobLock)
        .where(JobLock.name == name, JobLock.owner == owner)
        .values(heartbeat_at=utcnow())
    )
    result = db.execute(stmt)
    if commit:
        db.commit()
    return result.rowcount == 1


def recover_stale_locks(
    name: str,
    ttl: timedelta = LOCK_HEARTBEAT_TTL,
    *,
    run_type: str | None = None,
) -> None:
    """Release locks whose owner crashed and finalise the orphaned runs.

    Called from the FastAPI lifespan on every startup. Any run that was
    interrupted is also marked as ``phase=finished / status=error`` so the UI
    does not keep showing a perpetually-running run.

    Parameters
    ----------
    name:
        Name of the ``JobLock`` row to check.
    ttl:
        Heartbeat TTL; locks whose heartbeat is older than this are reclaimed.
    run_type:
        When provided, only finalises ``RunLog`` rows with a matching
        ``run_type``.  Pass ``"market"`` to restrict recovery to market-data
        runs (including legacy rows where ``run_type`` is ``NULL``), or
        ``"jobs"`` to restrict to job-scrape runs.  The default ``None``
        finalises all stuck runs regardless of type (backward-compatible
        behaviour).
    """
    db = SessionLocal()
    try:
        lock = db.get(JobLock, name)
        if lock and is_lock_stale(lock, ttl):
            logger.warning(
                "Reclaiming stale lock %s (owner=%s, heartbeat=%s)",
                name,
                lock.owner,
                lock.heartbeat_at,
            )
            lock.locked = False
            lock.owner = None
            db.add(lock)
            query = db.query(RunLog).filter(RunLog.phase.in_(("queued", "running")))
            if run_type == "market":
                # Include legacy rows created before the run_type column was
                # added (NULL) as well as rows explicitly tagged "market".
                query = query.filter(
                    (RunLog.run_type == "market") | RunLog.run_type.is_(None)
                )
            elif run_type is not None:
                query = query.filter(RunLog.run_type == run_type)
            for stuck in query.all():
                stuck.phase = "finished"
                stuck.status = "error"
                stuck.finished_at = utcnow()
                stuck.error_details = (stuck.error_details or "") + "\nrecovered after crash"
                db.add(stuck)
            db.commit()
    finally:
        db.close()
