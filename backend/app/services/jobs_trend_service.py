"""Read-only analytics over `JobSnapshot` rows.

Used by the API to surface the latest count + n-day deltas without forcing
each route to handcraft the same aggregations.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.job_source import JobSnapshot, JobSource


def latest_snapshot(db: Session, source_id: int) -> JobSnapshot | None:
    return (
        db.query(JobSnapshot)
        .filter(JobSnapshot.job_source_id == source_id)
        .order_by(JobSnapshot.snapshot_date.desc())
        .first()
    )


def latest_snapshots_by_source(
    db: Session, source_ids: list[int]
) -> dict[int, JobSnapshot]:
    """Batched lookup so list endpoints avoid N+1 queries."""
    if not source_ids:
        return {}
    # Sub-query that picks the max date per source. SQLite + Postgres-friendly.
    sub = (
        db.query(
            JobSnapshot.job_source_id.label("sid"),
            func.max(JobSnapshot.snapshot_date).label("max_date"),
        )
        .filter(JobSnapshot.job_source_id.in_(source_ids))
        .group_by(JobSnapshot.job_source_id)
        .subquery()
    )
    rows = (
        db.query(JobSnapshot)
        .join(
            sub,
            (JobSnapshot.job_source_id == sub.c.sid)
            & (JobSnapshot.snapshot_date == sub.c.max_date),
        )
        .all()
    )
    return {row.job_source_id: row for row in rows}


def trend_for_source(
    db: Session, source_id: int, *, days: int = 30
) -> list[JobSnapshot]:
    cutoff = utcnow().date() - timedelta(days=days)
    return (
        db.query(JobSnapshot)
        .filter(
            JobSnapshot.job_source_id == source_id,
            JobSnapshot.snapshot_date >= cutoff,
        )
        .order_by(JobSnapshot.snapshot_date.asc())
        .all()
    )


def delta_for_source(db: Session, source_id: int, *, days: int) -> int | None:
    """Difference between the latest count and the count ``days`` ago.

    Returns ``None`` when either endpoint is missing — the UI then renders
    "–" instead of a misleading zero.
    """
    latest = latest_snapshot(db, source_id)
    if latest is None:
        return None
    target = latest.snapshot_date - timedelta(days=days)
    earlier = (
        db.query(JobSnapshot)
        .filter(
            JobSnapshot.job_source_id == source_id,
            JobSnapshot.snapshot_date <= target,
        )
        .order_by(JobSnapshot.snapshot_date.desc())
        .first()
    )
    if earlier is None:
        return None
    return latest.jobs_count - earlier.jobs_count


def summary_for_source(db: Session, source_id: int) -> dict[str, Any]:
    latest = latest_snapshot(db, source_id)
    return {
        "latest_count": latest.jobs_count if latest else None,
        "latest_snapshot_date": latest.snapshot_date.isoformat() if latest else None,
        "delta_7d": delta_for_source(db, source_id, days=7),
        "delta_30d": delta_for_source(db, source_id, days=30),
    }


def trend_for_isin(
    db: Session, isin: str, *, days: int = 90
) -> list[tuple[date, int]]:
    """Per-day summed jobs_count across all *active* sources of one ISIN.

    Only active sources are included so that disabled portals do not skew
    the aggregate (same rule as ``aggregated_trends_by_isin``).
    Returns an empty list when the ISIN has no matching snapshots.
    """
    cutoff = utcnow().date() - timedelta(days=days)
    rows = (
        db.query(
            JobSnapshot.snapshot_date,
            func.sum(JobSnapshot.jobs_count).label("total"),
        )
        .join(JobSource, JobSnapshot.job_source_id == JobSource.id)
        .filter(
            JobSource.isin == isin,
            JobSource.is_active.is_(True),
            JobSnapshot.snapshot_date >= cutoff,
        )
        .group_by(JobSnapshot.snapshot_date)
        .order_by(JobSnapshot.snapshot_date.asc())
        .all()
    )
    return [(snap_date, int(total)) for snap_date, total in rows]


def aggregated_trends_by_isin(
    db: Session, *, days: int = 90
) -> dict[str, list[tuple[date, int]]]:
    """Return per-ISIN, per-day summed `jobs_count` over the last ``days``.

    Used by the watchlist sparkline column: a single aggregate query so we
    avoid an N+1 fan-out when the watchlist is large. Sources without an
    ISIN (manually tracked, not on the watchlist) and inactive sources are
    excluded — the same scope the column-level aggregate already uses.
    """
    cutoff = utcnow().date() - timedelta(days=days)
    rows = (
        db.query(
            JobSource.isin,
            JobSnapshot.snapshot_date,
            func.sum(JobSnapshot.jobs_count).label("total"),
        )
        .join(JobSnapshot, JobSnapshot.job_source_id == JobSource.id)
        .filter(
            JobSource.isin.isnot(None),
            JobSource.is_active.is_(True),
            JobSnapshot.snapshot_date >= cutoff,
        )
        .group_by(JobSource.isin, JobSnapshot.snapshot_date)
        .order_by(JobSource.isin, JobSnapshot.snapshot_date.asc())
        .all()
    )
    out: dict[str, list[tuple[date, int]]] = {}
    for isin, snap_date, total in rows:
        out.setdefault(isin, []).append((snap_date, int(total)))
    return out
