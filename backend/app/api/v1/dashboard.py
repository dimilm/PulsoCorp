from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.run_log import RunLog
from app.services.stock_service import list_stocks

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    stocks = list_stocks(db)
    sorted_by_change = sorted([s for s in stocks if s.get("day_change_pct") is not None], key=lambda s: s["day_change_pct"])
    losers = sorted_by_change[:5]
    winners = list(reversed(sorted_by_change[-5:]))
    candidates = [s for s in stocks if s["recommendation"] == "buy" and ((s.get("dcf_discount_pct") or 0) < 0)]
    invested = sum(s["invested_capital_eur"] for s in stocks)
    moat_invested = sum(s["invested_capital_eur"] for s in stocks if s["burggraben"])
    portfolio_day_change_eur = sum(
        (s["invested_capital_eur"] * (s["day_change_pct"] or 0) / 100) for s in stocks if s["day_change_pct"] is not None
    )
    portfolio_value_eur = invested + portfolio_day_change_eur
    portfolio_day_change_pct = (portfolio_day_change_eur / invested * 100) if invested else 0
    last_run = db.query(RunLog).order_by(RunLog.started_at.desc()).first()
    return {
        "total_stocks": len(stocks),
        "total_invested_eur": invested,
        "portfolio_value_eur": portfolio_value_eur,
        "portfolio_day_change_eur": portfolio_day_change_eur,
        "portfolio_day_change_pct": portfolio_day_change_pct,
        "moat_share_pct": (moat_invested / invested * 100) if invested else 0,
        "winners": winners,
        "losers": losers,
        "buy_candidates": candidates[:10],
        "last_run": {
            "id": last_run.id if last_run else None,
            "started_at": last_run.started_at if last_run else None,
            "finished_at": last_run.finished_at if last_run else None,
            "phase": last_run.phase if last_run else None,
            "status": last_run.status if last_run else None,
            "stocks_total": last_run.stocks_total if last_run else 0,
            "stocks_done": last_run.stocks_done if last_run else 0,
            "stocks_success": last_run.stocks_success if last_run else 0,
            "stocks_error": last_run.stocks_error if last_run else 0,
        },
    }
