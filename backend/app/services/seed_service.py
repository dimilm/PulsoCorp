import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.job_source import JobSource
from app.services.stock_service import upsert_seed_row


def load_seed_json(db: Session, seed_path: str) -> int:
    path = Path(seed_path)
    if not path.exists():
        return 0

    rows = json.loads(path.read_text(encoding="utf-8"))
    imported = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if "isin" not in row or "name" not in row:
            continue
        upsert_seed_row(db, row)
        imported += 1
    db.commit()
    return imported


def load_job_sources_seed_json(db: Session, seed_path: str) -> int:
    """Idempotent loader for the career-portal seed file.

    Each entry is upserted by ``(name, portal_url)`` so re-running the loader
    after editing the seed file simply updates existing rows. Required keys:
    ``name``, ``portal_url``, ``adapter_type``, ``adapter_settings``. Optional:
    ``isin`` (link to a watchlist stock) and ``is_active``.
    """
    path = Path(seed_path)
    if not path.exists():
        return 0

    rows = json.loads(path.read_text(encoding="utf-8"))
    imported = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        required = ("name", "portal_url", "adapter_type")
        if any(key not in row for key in required):
            continue

        existing = (
            db.query(JobSource)
            .filter(
                JobSource.name == row["name"],
                JobSource.portal_url == row["portal_url"],
            )
            .one_or_none()
        )
        if existing is None:
            db.add(
                JobSource(
                    isin=row.get("isin"),
                    name=row["name"],
                    portal_url=row["portal_url"],
                    adapter_type=row["adapter_type"],
                    adapter_settings=row.get("adapter_settings", {}),
                    is_active=row.get("is_active", True),
                )
            )
        else:
            existing.isin = row.get("isin", existing.isin)
            existing.adapter_type = row["adapter_type"]
            existing.adapter_settings = row.get("adapter_settings", {})
            if "is_active" in row:
                existing.is_active = row["is_active"]
            db.add(existing)
        imported += 1
    db.commit()
    return imported
