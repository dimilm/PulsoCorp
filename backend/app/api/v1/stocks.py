from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user, get_market_provider, require_admin
from app.db.session import get_db
from app.models.job_source import JobSource
from app.models.stock import Stock
from app.providers.market.base import MarketProvider
from app.schemas.job_source import JobsAggregateTrendPoint, StockJobsOut, StockJobsTrendOut
from app.schemas.stock import HistoryResponse, SectorSuggestion, StockCreate, StockOut, StockUpdate
from app.services import jobs_trend_service
from app.services.history_service import HistoryService
from app.services.scheduler_service import start_single_refresh_background
from app.services.stock_service import (
    create_stock,
    find_similar_stocks,
    list_stocks,
    to_stock_out,
    update_stock,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=list[StockOut])
def get_stocks(
    query: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    tags: str | None = Query(default=None),
    tags_mode: str = Query(default="any", pattern="^(any|all)$"),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    return list_stocks(
        db,
        query=query,
        sector=sector,
        tags=tag_list,
        tags_mode=tags_mode,
    )


@router.post("", response_model=StockOut, dependencies=[Depends(csrf_guard)])
def post_stock(payload: StockCreate, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stock = create_stock(db, payload)
    return to_stock_out(db, stock)


@router.get("/sectors", response_model=list[SectorSuggestion])
def get_sectors(
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = (
        db.query(Stock.sector, func.count(Stock.isin).label("count"))
        .filter(Stock.sector.isnot(None), Stock.sector != "")
        .group_by(Stock.sector)
        .order_by(Stock.sector.asc())
        .all()
    )
    return [{"name": row.sector, "count": row.count} for row in rows]


@router.get("/{isin}", response_model=StockOut)
def get_stock(isin: str, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return to_stock_out(db, stock)


@router.patch("/{isin}", response_model=StockOut, dependencies=[Depends(csrf_guard)])
def patch_stock(isin: str, payload: StockUpdate, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    stock = update_stock(db, stock, payload)
    return to_stock_out(db, stock)


@router.delete("/{isin}", dependencies=[Depends(csrf_guard)])
def delete_stock(isin: str, _: dict = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    db.delete(stock)
    db.commit()
    return {"ok": True}


@router.post("/{isin}/refresh", dependencies=[Depends(csrf_guard)])
def refresh_stock(isin: str, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Kick off a background market-data refresh for a single stock.

    Returns immediately with the new run id so the UI can poll
    `/run-logs/current` and `/run-logs/{run_id}/stocks` for live progress
    (same plumbing as the bulk refresh).
    """
    isin_upper = isin.upper()
    if not db.get(Stock, isin_upper):
        raise HTTPException(status_code=404, detail="Stock not found")
    return start_single_refresh_background(isin_upper)


@router.get("/{isin}/history", response_model=HistoryResponse)
async def get_stock_history(
    isin: str,
    range: str = Query(default="1y", pattern="^(1m|6m|1y|5y|max)$"),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    market_provider: MarketProvider = Depends(get_market_provider),
) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    service = HistoryService(market_provider)
    result = await service.get_history(db, stock, range)
    return {"isin": stock.isin, **result}


@router.get("/{isin}/similar", response_model=list[StockOut])
def get_stock_similar(
    isin: str,
    limit: int = Query(default=5, ge=1, le=20),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return find_similar_stocks(db, stock, limit)


@router.get("/{isin}/jobs", response_model=StockJobsOut)
def get_stock_jobs(
    isin: str,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Return all job sources attached to ``isin`` plus aggregated counts.

    Used by the StockDetailPage `Offene Stellen` section. When the stock
    has multiple sources (e.g. Volkswagen Group with several portals), the
    UI can render each one individually and the totals fall out of summing
    the per-source latest counts.
    """
    isin_upper = isin.upper()
    stock = db.get(Stock, isin_upper)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    sources = (
        db.query(JobSource)
        .filter(JobSource.isin == isin_upper)
        .order_by(JobSource.name.asc())
        .all()
    )

    out_sources: list[dict] = []
    total_latest = 0
    total_d7 = 0
    total_d30 = 0
    has_latest = False
    has_d7 = False
    has_d30 = False
    for source in sources:
        summary = jobs_trend_service.summary_for_source(db, source.id)
        out_sources.append(
            {
                "id": source.id,
                "isin": source.isin,
                "name": source.name,
                "portal_url": source.portal_url,
                "adapter_type": source.adapter_type,
                "adapter_settings": source.adapter_settings or {},
                "is_active": source.is_active,
                "created_at": source.created_at,
                "updated_at": source.updated_at,
                **summary,
            }
        )
        if summary["latest_count"] is not None:
            total_latest += summary["latest_count"]
            has_latest = True
        if summary["delta_7d"] is not None:
            total_d7 += summary["delta_7d"]
            has_d7 = True
        if summary["delta_30d"] is not None:
            total_d30 += summary["delta_30d"]
            has_d30 = True

    return {
        "isin": isin_upper,
        "sources": out_sources,
        "total_latest": total_latest if has_latest else None,
        "total_delta_7d": total_d7 if has_d7 else None,
        "total_delta_30d": total_d30 if has_d30 else None,
    }


@router.get("/{isin}/jobs/trend", response_model=StockJobsTrendOut)
def get_stock_jobs_trend(
    isin: str,
    days: int = Query(default=90, ge=1, le=3650),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Per-day summed open-position count across all active job sources for ``isin``.

    The time window is controlled by ``days`` (default 90, max 10 years).
    Returns an empty ``points`` list — not a 404 — when the stock has no
    active sources or no snapshots yet, so the frontend can render a
    "no data" state without special-casing HTTP errors.
    """
    isin_upper = isin.upper()
    if not db.get(Stock, isin_upper):
        raise HTTPException(status_code=404, detail="Stock not found")
    points = jobs_trend_service.trend_for_isin(db, isin_upper, days=days)
    return {
        "isin": isin_upper,
        "days": days,
        "points": [
            JobsAggregateTrendPoint(snapshot_date=snap_date, jobs_count=count)
            for snap_date, count in points
        ],
    }
