from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user, require_admin
from app.db.session import get_db
from app.models.stock import Stock, Valuation
from app.providers.market.yfinance_provider import YFinanceProvider
from app.schemas.stock import LockRequest, StockCreate, StockOut, StockUpdate
from app.services.market_service import MarketService
from app.services.stock_service import create_stock, list_stocks, to_stock_out, update_stock

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=list[StockOut])
def get_stocks(
    query: str | None = Query(default=None),
    sector: str | None = Query(default=None),
    recommendation: str | None = Query(default=None),
    burggraben: bool | None = Query(default=None),
    score_min: int | None = Query(default=None),
    score_max: int | None = Query(default=None),
    undervalued_dcf: bool | None = Query(default=None),
    undervalued_nav: bool | None = Query(default=None),
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
        recommendation=recommendation,
        burggraben=burggraben,
        score_min=score_min,
        score_max=score_max,
        undervalued_dcf=undervalued_dcf,
        undervalued_nav=undervalued_nav,
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
async def refresh_stock(isin: str, _: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    service = MarketService(YFinanceProvider())
    try:
        await service.refresh_stock(db, stock)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Refresh failed: {exc}") from exc
    return {"ok": True}


@router.post("/{isin}/lock", dependencies=[Depends(csrf_guard)])
def lock_fields(
    isin: str, payload: LockRequest, _: dict = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    valuation = db.get(Valuation, isin.upper()) or Valuation(isin=isin.upper(), field_sources={}, field_locks={})
    for field_name in payload.field_names:
        valuation.field_locks[field_name] = payload.locked
    db.add(valuation)
    db.commit()
    return {"ok": True, "locks": valuation.field_locks}
