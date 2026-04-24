from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user, require_admin
from app.db.session import get_db
from app.models.stock import Stock
from app.providers.market.yfinance_provider import YFinanceProvider
from app.schemas.stock import HistoryResponse, StockCreate, StockOut, StockUpdate
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
    burggraben: bool | None = Query(default=None),
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
        burggraben=burggraben,
        tags=tag_list,
        tags_mode=tags_mode,
    )


@router.post("", response_model=StockOut, dependencies=[Depends(csrf_guard)])
def post_stock(payload: StockCreate, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stock = create_stock(db, payload)
    return to_stock_out(db, stock)


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
) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    service = HistoryService(YFinanceProvider())
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
