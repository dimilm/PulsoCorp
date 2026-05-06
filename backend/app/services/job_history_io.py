"""CSV export/import for the full `JobSnapshot` history across all job sources.

Export shape (one row per snapshot, all sources, all days):
    job_source_id,isin,source_name,snapshot_date,jobs_count

Import matching order per row:  job_source_id  →  source_name (case-insensitive)  →  isin.
Conflict policy: skip — existing snapshots are never overwritten.

The ISIN fallback is only used when exactly one *active* source carries that
ISIN; if multiple sources share the ISIN (e.g. Volkswagen with two portals)
the row is reported as unmapped with reason ``isin_ambiguous`` so the user
can fix it by filling in either ``job_source_id`` or ``source_name``.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.job_source import JobSnapshot, JobSource


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------

class UnmappedRow(BaseModel):
    row: dict[str, str]
    reason: str


class MalformedRow(BaseModel):
    row: dict[str, str]
    error: str


class ImportReport(BaseModel):
    total_rows: int
    inserted: int
    skipped_existing: int
    unmapped_rows: list[UnmappedRow]
    malformed_rows: list[MalformedRow]


# ---------------------------------------------------------------------------
# CSV columns (canonical order)
# ---------------------------------------------------------------------------

_FIELDNAMES = ["job_source_id", "isin", "source_name", "snapshot_date", "jobs_count"]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def build_history_csv(db: Session) -> str:
    """Return the full job-snapshot history as a UTF-8 CSV string.

    Sorted by source_name asc, snapshot_date asc so repeated exports produce
    deterministic output suitable for ``git diff``.
    """
    rows = (
        db.query(
            JobSource.id.label("job_source_id"),
            JobSource.isin.label("isin"),
            JobSource.name.label("source_name"),
            JobSnapshot.snapshot_date.label("snapshot_date"),
            JobSnapshot.jobs_count.label("jobs_count"),
        )
        .join(JobSnapshot, JobSnapshot.job_source_id == JobSource.id)
        .order_by(JobSource.name.asc(), JobSnapshot.snapshot_date.asc())
        .all()
    )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "job_source_id": row.job_source_id,
                "isin": row.isin or "",
                "source_name": row.source_name,
                "snapshot_date": (
                    row.snapshot_date.isoformat()
                    if isinstance(row.snapshot_date, date)
                    else row.snapshot_date
                ),
                "jobs_count": row.jobs_count,
            }
        )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _build_source_indices(
    db: Session,
) -> tuple[dict[int, JobSource], dict[str, JobSource], dict[str, list[JobSource]]]:
    """Return three lookup indices built from all sources in the DB.

    Returns:
        by_id   — {source.id: source}
        by_name — {source.name.lower(): source}  (last writer wins for dupes)
        by_isin — {source.isin: [source, ...]}   (includes all sources per ISIN)
    """
    sources = db.query(JobSource).all()
    by_id: dict[int, JobSource] = {}
    by_name: dict[str, JobSource] = {}
    by_isin: dict[str, list[JobSource]] = defaultdict(list)

    for s in sources:
        by_id[s.id] = s
        by_name[s.name.lower()] = s
        if s.isin:
            by_isin[s.isin.upper()].append(s)

    return by_id, by_name, by_isin


def _existing_dates(db: Session, source_id: int) -> set[date]:
    """Return the set of snapshot_dates already present for a source."""
    rows = (
        db.query(JobSnapshot.snapshot_date)
        .filter(JobSnapshot.job_source_id == source_id)
        .all()
    )
    return {r[0] for r in rows}


def import_history_csv(db: Session, content: bytes) -> ImportReport:
    """Parse *content* (raw CSV bytes) and insert new snapshots.

    Matching order per row:
        1. ``job_source_id`` (int) — exact match against source IDs in the DB.
        2. ``source_name`` (case-insensitive) — fall back when ID is absent/0/unknown.
        3. ``isin`` — fall back when name is also absent; only when exactly one
           active source carries that ISIN.

    Rows that cannot be resolved are collected in ``unmapped_rows``.
    Rows with invalid field values (bad date, negative count, …) are collected
    in ``malformed_rows``.  Both sets are included in the returned report;
    the caller never sees an exception for individual bad rows.
    """
    try:
        text = content.decode("utf-8-sig")  # handle Excel BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    by_id, by_name, by_isin = _build_source_indices(db)

    # Cache existing dates per source so the duplicate check is O(1).
    existing: dict[int, set[date]] = {}

    reader = csv.DictReader(io.StringIO(text))

    total_rows = 0
    inserted = 0
    skipped_existing = 0
    unmapped_rows: list[UnmappedRow] = []
    malformed_rows: list[MalformedRow] = []

    to_insert: list[dict[str, Any]] = []

    for raw in reader:
        total_rows += 1
        row = {k.strip(): (v or "").strip() for k, v in raw.items()}

        # ------------------------------------------------------------------ #
        # 1. Resolve the source                                               #
        # ------------------------------------------------------------------ #
        source: JobSource | None = None

        id_str = row.get("job_source_id", "")
        if id_str:
            try:
                sid = int(id_str)
                source = by_id.get(sid)
            except ValueError:
                malformed_rows.append(
                    MalformedRow(row=row, error=f"job_source_id is not an integer: {id_str!r}")
                )
                continue

        if source is None:
            name_key = row.get("source_name", "").lower()
            if name_key:
                source = by_name.get(name_key)

        if source is None:
            isin_key = row.get("isin", "").upper()
            if isin_key:
                candidates = by_isin.get(isin_key, [])
                if len(candidates) == 1:
                    source = candidates[0]
                elif len(candidates) > 1:
                    unmapped_rows.append(
                        UnmappedRow(
                            row=row,
                            reason=(
                                f"isin_ambiguous: ISIN {isin_key!r} matches "
                                f"{len(candidates)} sources — specify job_source_id or source_name"
                            ),
                        )
                    )
                    continue

        if source is None:
            unmapped_rows.append(
                UnmappedRow(row=row, reason="no matching source for id/name/isin")
            )
            continue

        # ------------------------------------------------------------------ #
        # 2. Validate snapshot_date and jobs_count                            #
        # ------------------------------------------------------------------ #
        date_str = row.get("snapshot_date", "")
        if not date_str:
            malformed_rows.append(MalformedRow(row=row, error="snapshot_date is missing"))
            continue
        try:
            snap_date = date.fromisoformat(date_str)
        except ValueError:
            malformed_rows.append(
                MalformedRow(row=row, error=f"snapshot_date is not a valid ISO date: {date_str!r}")
            )
            continue

        count_str = row.get("jobs_count", "")
        if not count_str:
            malformed_rows.append(MalformedRow(row=row, error="jobs_count is missing"))
            continue
        try:
            jobs_count = int(count_str)
        except ValueError:
            malformed_rows.append(
                MalformedRow(row=row, error=f"jobs_count is not an integer: {count_str!r}")
            )
            continue
        if jobs_count < 0:
            malformed_rows.append(
                MalformedRow(row=row, error=f"jobs_count must be >= 0, got {jobs_count}")
            )
            continue

        # ------------------------------------------------------------------ #
        # 3. Skip-on-conflict check                                           #
        # ------------------------------------------------------------------ #
        if source.id not in existing:
            existing[source.id] = _existing_dates(db, source.id)

        if snap_date in existing[source.id]:
            skipped_existing += 1
            continue

        # Mark as pending in the in-memory set so the same (source, date) pair
        # from within the same CSV does not get double-inserted.
        existing[source.id].add(snap_date)
        to_insert.append(
            {
                "job_source_id": source.id,
                "snapshot_date": snap_date,
                "jobs_count": jobs_count,
                "raw_meta": {},
            }
        )
        inserted += 1

    if to_insert:
        db.bulk_insert_mappings(JobSnapshot, to_insert)
        db.commit()

    return ImportReport(
        total_rows=total_rows,
        inserted=inserted,
        skipped_existing=skipped_existing,
        unmapped_rows=unmapped_rows,
        malformed_rows=malformed_rows,
    )
