"""Helpers around `RunStockStatus` rows for live progress tracking.

The scheduler writes one row per stock per refresh run and updates it as the
individual steps progress. The frontend polls these rows to show live progress.

Retention: only the two most recent runs keep their per-stock detail rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.run_log import RunLog, RunStockStatus
from app.models.stock import Stock

STEP_FIELDS = ("symbol", "quote", "metrics", "ai")


def humanize_error(exc: Exception) -> str:
    """Map common provider/library errors to short, user-friendly text."""
    message = str(exc).strip() or exc.__class__.__name__
    lower = message.lower()
    if "symbol" in lower and ("not" in lower or "invalid" in lower):
        return "Ticker nicht gefunden"
    if "404" in lower or "not found" in lower:
        return "Daten nicht gefunden"
    if "timeout" in lower or "timed out" in lower:
        return "Zeitüberschreitung beim Abruf"
    if "rate" in lower and "limit" in lower:
        return "Rate-Limit erreicht"
    if "connection" in lower or "network" in lower:
        return "Verbindungsfehler"
    if len(message) > 240:
        return message[:237] + "..."
    return message


def init_run_stocks(db: Session, run_id: int, stocks: Iterable[Stock]) -> int:
    """Create one `RunStockStatus` row per stock for the given run.

    Returns the number of rows created.
    """
    count = 0
    for stock in stocks:
        db.add(
            RunStockStatus(
                run_id=run_id,
                isin=stock.isin,
                stock_name=stock.name,
                resolved_symbol=stock.ticker_override,
            )
        )
        count += 1
    db.commit()
    return count


def cleanup_old_run_status(db: Session, keep_run_ids: Iterable[int]) -> int:
    """Delete `RunStockStatus` rows that don't belong to one of the kept runs."""
    keep = list(keep_run_ids)
    if not keep:
        return 0
    deleted = (
        db.query(RunStockStatus)
        .filter(~RunStockStatus.run_id.in_(keep))
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


def two_most_recent_run_ids(db: Session) -> list[int]:
    rows = db.query(RunLog.id).order_by(RunLog.id.desc()).limit(2).all()
    return [r.id for r in rows]


def get_status_row(db: Session, run_id: int, isin: str) -> RunStockStatus | None:
    return (
        db.query(RunStockStatus)
        .filter(RunStockStatus.run_id == run_id, RunStockStatus.isin == isin)
        .one_or_none()
    )


def mark_stock_running(row: RunStockStatus) -> None:
    row.overall_status = "running"
    row.started_at = datetime.utcnow()


def mark_step_running(row: RunStockStatus, step: str) -> None:
    setattr(row, f"{step}_status", "running")
    setattr(row, f"{step}_started_at", datetime.utcnow())
    setattr(row, f"{step}_error", None)


def mark_step_done(row: RunStockStatus, step: str) -> None:
    setattr(row, f"{step}_status", "done")
    setattr(row, f"{step}_finished_at", datetime.utcnow())


def mark_step_error(row: RunStockStatus, step: str, error: Exception | str) -> None:
    setattr(row, f"{step}_status", "error")
    setattr(row, f"{step}_finished_at", datetime.utcnow())
    if isinstance(error, Exception):
        setattr(row, f"{step}_error", humanize_error(error))
    else:
        setattr(row, f"{step}_error", str(error))


def mark_stock_finished(row: RunStockStatus, success: bool) -> None:
    row.overall_status = "done" if success else "error"
    row.finished_at = datetime.utcnow()
