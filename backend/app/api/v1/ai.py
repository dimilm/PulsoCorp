from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user
from app.db.session import get_db
from app.models.settings import AppSettings
from app.models.stock import Stock
from app.services.ai_service import AIService
from app.services.provider_factory import build_ai_provider

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/evaluate/{isin}", dependencies=[Depends(csrf_guard)])
async def evaluate_stock(
    isin: str, apply: bool = False, _: dict = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    stock = db.get(Stock, isin.upper())
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    app_settings = db.get(AppSettings, 1) or AppSettings(id=1)
    service = AIService(build_ai_provider(app_settings))
    valuation = await service.evaluate_stock(db, stock, force=True, apply=apply)
    if apply:
        db.commit()
    return {
        "ok": True,
        "applied": apply,
        "fundamental_score": valuation.fundamental_score,
        "moat_score": valuation.moat_score,
        "moat_text": valuation.moat_text,
        "fair_value_dcf": valuation.fair_value_dcf,
        "fair_value_nav": valuation.fair_value_nav,
        "recommendation": valuation.recommendation,
        "recommendation_reason": valuation.recommendation_reason,
        "risk_notes": valuation.risk_notes,
        "estimated_cost": valuation.ai_cost_estimate,
    }
