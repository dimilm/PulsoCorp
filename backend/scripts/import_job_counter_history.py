"""Backfill `job_snapshots` from the legacy ``11_JobCounter`` snapshot files.

Each ``data/snapshots/YYYY-MM-DD.json`` file holds one entry per company that
the standalone JobCounter scraped on that day. We map each entry to a
``JobSource`` row in CompanyTracker (looked up by name) and insert one
``JobSnapshot`` per (source, day). Duplicate keys are skipped so the script
is idempotent and can be re-run after a partial import.

Usage::

    conda activate companytracker
    python scripts/import_job_counter_history.py \
        --snapshots ../11_JobCounter/01_JobCounter/data/snapshots
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

# Allow running from outside the backend dir.
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.db.session import SessionLocal  # noqa: E402  (import after sys.path tweak)
from app.models.job_source import JobSnapshot, JobSource  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshots",
        type=Path,
        required=True,
        help="Path to the JobCounter data/snapshots directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and resolve sources but do not write to the database.",
    )
    return parser.parse_args()


def _resolve_sources(db) -> dict[str, JobSource]:
    """Return a {lowercase-name: JobSource} map for fuzzy lookup.

    The legacy file references companies by their human-readable name (e.g.
    "Deutsche Bank") and free-form id ("deutsche_bank"). The ported seed
    keeps the same names, so a case-insensitive match on ``name`` is
    sufficient for the curated set we ship.
    """
    sources = db.query(JobSource).all()
    return {s.name.lower(): s for s in sources}


def _import_snapshot_file(
    db, file_path: Path, sources_by_name: dict[str, JobSource], *, dry_run: bool
) -> tuple[int, int, list[str]]:
    payload: list[dict[str, Any]] = json.loads(file_path.read_text(encoding="utf-8"))
    inserted = 0
    skipped = 0
    unmapped: list[str] = []

    for entry in payload:
        company_name = entry.get("company_name") or entry.get("company_id")
        snapshot_date_raw = entry.get("snapshot_date")
        jobs_count = entry.get("jobs_count")
        if not company_name or not snapshot_date_raw or jobs_count is None:
            skipped += 1
            continue

        source = sources_by_name.get(company_name.lower())
        if source is None:
            unmapped.append(company_name)
            skipped += 1
            continue

        try:
            snapshot_date = date.fromisoformat(snapshot_date_raw)
        except ValueError:
            skipped += 1
            continue

        # Skip if already imported (UNIQUE on (source_id, snapshot_date)).
        already_present = (
            db.query(JobSnapshot)
            .filter(
                JobSnapshot.job_source_id == source.id,
                JobSnapshot.snapshot_date == snapshot_date,
            )
            .first()
            is not None
        )
        if already_present:
            skipped += 1
            continue

        if not dry_run:
            db.add(
                JobSnapshot(
                    job_source_id=source.id,
                    snapshot_date=snapshot_date,
                    jobs_count=int(jobs_count),
                    raw_meta=entry.get("raw_meta", {}) or {},
                )
            )
        inserted += 1

    if not dry_run:
        db.commit()
    return inserted, skipped, unmapped


def main() -> None:
    args = _parse_args()
    if not args.snapshots.exists() or not args.snapshots.is_dir():
        raise SystemExit(f"Snapshots directory not found: {args.snapshots}")

    db = SessionLocal()
    try:
        sources_by_name = _resolve_sources(db)
        if not sources_by_name:
            raise SystemExit(
                "No JobSource rows found. Run the YAML→seed import first or "
                "start the backend once so the seed loads."
            )

        total_inserted = 0
        total_skipped = 0
        unmapped_companies: set[str] = set()

        for json_file in sorted(args.snapshots.glob("*.json")):
            inserted, skipped, unmapped = _import_snapshot_file(
                db, json_file, sources_by_name, dry_run=args.dry_run
            )
            total_inserted += inserted
            total_skipped += skipped
            unmapped_companies.update(unmapped)
            print(
                f"{json_file.name}: inserted={inserted}, "
                f"skipped={skipped}, unmapped={len(unmapped)}"
            )

        print(
            f"\nTotal: inserted={total_inserted}, skipped={total_skipped}"
            f"{' (dry-run)' if args.dry_run else ''}"
        )
        if unmapped_companies:
            print("Unmapped company names (no matching JobSource):")
            for name in sorted(unmapped_companies):
                print(f"  - {name}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
