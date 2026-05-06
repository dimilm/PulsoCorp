from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.job_source import JobSource, RunJobStatus
from app.models.run_log import RunLog, RunStockStatus
from app.models.stock import Stock
from app.schemas.job_source import RunJobStatusOut
from app.schemas.run_log import RunLogOut, RunStockStatusOut, RunStockStepOut

router = APIRouter(prefix="/run-logs", tags=["run-logs"])


@router.get("", response_model=list[RunLogOut])
def list_run_logs(
    run_type: str | None = Query(default=None, pattern="^(market|jobs)$"),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunLog]:
    query = db.query(RunLog)
    if run_type:
        query = query.filter(RunLog.run_type == run_type)
    return query.order_by(RunLog.started_at.desc()).limit(200).all()


@router.get("/current", response_model=RunLogOut | None)
def current_run(
    run_type: str | None = Query(default=None, pattern="^(market|jobs)$"),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunLog | None:
    """The most recently created run, optionally scoped to one ``run_type``.

    The frontend calls this on page load and during polling to know whether a
    refresh is in progress and which run id to inspect for per-stock detail.
    Without a filter the legacy behaviour (latest run of any type) is preserved.
    """
    query = db.query(RunLog)
    if run_type:
        query = query.filter(RunLog.run_type == run_type)
    return query.order_by(RunLog.id.desc()).first()


@router.get("/{run_id}", response_model=RunLogOut)
def get_run(run_id: int, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> RunLog:
    run = db.get(RunLog, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{run_id}/stocks", response_model=list[RunStockStatusOut])
def stocks_for_run(
    run_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunStockStatusOut]:
    if not db.get(RunLog, run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    rows = (
        db.query(RunStockStatus)
        .filter(RunStockStatus.run_id == run_id)
        .order_by(RunStockStatus.id.asc())
        .all()
    )
    if not rows:
        return []
    # If `stock_name` is missing for legacy rows, look it up so the UI is not
    # forced to make an extra request per row.
    missing_isins = [r.isin for r in rows if not r.stock_name]
    name_lookup: dict[str, str] = {}
    if missing_isins:
        name_lookup = {
            s.isin: s.name
            for s in db.query(Stock).filter(Stock.isin.in_(missing_isins)).all()
        }
    return [_to_status_out(row, name_lookup) for row in rows]


def _to_status_out(row: RunStockStatus, name_lookup: dict[str, str]) -> RunStockStatusOut:
    return RunStockStatusOut(
        isin=row.isin,
        stock_name=row.stock_name or name_lookup.get(row.isin),
        overall_status=row.overall_status,
        started_at=row.started_at,
        finished_at=row.finished_at,
        resolved_symbol=row.resolved_symbol,
        symbol=RunStockStepOut(
            status=row.symbol_status,
            started_at=row.symbol_started_at,
            finished_at=row.symbol_finished_at,
            error=row.symbol_error,
        ),
        quote=RunStockStepOut(
            status=row.quote_status,
            started_at=row.quote_started_at,
            finished_at=row.quote_finished_at,
            error=row.quote_error,
        ),
        metrics=RunStockStepOut(
            status=row.metrics_status,
            started_at=row.metrics_started_at,
            finished_at=row.metrics_finished_at,
            error=row.metrics_error,
        ),
    )


@router.get("/{run_id}/jobs", response_model=list[RunJobStatusOut])
def jobs_for_run(
    run_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RunJobStatusOut]:
    """Per-source progress detail for a ``run_type='jobs'`` RunLog."""
    run = db.get(RunLog, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.run_type != "jobs":
        # Returning an empty list for the wrong run type would be confusing;
        # surface the mismatch so the UI can fall back to the stock view.
        raise HTTPException(
            status_code=400, detail="Run is not a jobs run"
        )

    rows = (
        db.query(RunJobStatus)
        .filter(RunJobStatus.run_id == run_id)
        .order_by(RunJobStatus.id.asc())
        .all()
    )
    if not rows:
        return []

    # Backfill source_name for legacy rows the same way we do for stocks.
    missing_ids = [r.job_source_id for r in rows if not r.source_name]
    name_lookup: dict[int, str] = {}
    if missing_ids:
        name_lookup = {
            s.id: s.name
            for s in db.query(JobSource).filter(JobSource.id.in_(missing_ids)).all()
        }

    return [
        RunJobStatusOut(
            job_source_id=row.job_source_id,
            source_name=row.source_name or name_lookup.get(row.job_source_id),
            isin=row.isin,
            overall_status=row.overall_status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            jobs_count=row.jobs_count,
            error=row.error,
        )
        for row in rows
    ]
