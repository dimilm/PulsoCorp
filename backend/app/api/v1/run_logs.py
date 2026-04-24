from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.run_log import RunLog, RunStockStatus
from app.models.stock import Stock
from app.schemas.run_log import RunLogOut, RunStockStatusOut, RunStockStepOut

router = APIRouter(prefix="/run-logs", tags=["run-logs"])


@router.get("", response_model=list[RunLogOut])
def list_run_logs(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RunLog]:
    return db.query(RunLog).order_by(RunLog.started_at.desc()).limit(200).all()


@router.get("/current", response_model=RunLogOut | None)
def current_run(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> RunLog | None:
    """The most recently created run, regardless of phase.

    The frontend calls this on page load and during polling to know whether a
    refresh is in progress and which run id to inspect for per-stock detail.
    """
    return db.query(RunLog).order_by(RunLog.id.desc()).first()


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
