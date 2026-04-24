from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.stock import MarketData, Metrics, Stock, Valuation
from app.providers.ai.base import AIProvider
from app.services.valuation_service import calc_discount_pct

# Source tags written into `Valuation.field_sources`. They mirror the legend in
# `Anforderungen.md` (M / L / B / KI) and add an explicit "ki_fallback" so the
# UI can distinguish heuristic values from real LLM answers.
SOURCE_AI = "ki"
SOURCE_AI_FALLBACK = "ki_fallback"


class AIService:
    def __init__(self, provider: AIProvider):
        self.provider = provider

    async def evaluate_stock(
        self, db: Session, stock: Stock, refresh_days: int = 30, force: bool = False, apply: bool = True
    ) -> Valuation:
        valuation = db.get(Valuation, stock.isin) or Valuation(isin=stock.isin)
        if not force and valuation.last_ai_at and valuation.last_ai_at > datetime.utcnow() - timedelta(days=refresh_days):
            return valuation

        market = db.get(MarketData, stock.isin)
        metrics = db.get(Metrics, stock.isin)
        payload = {
            "isin": stock.isin,
            "name": stock.name,
            "sector": stock.sector,
            "burggraben": stock.burggraben,
            "current_price": market.current_price if market else None,
            "pe_forward": metrics.pe_forward if metrics else None,
            "revenue_growth": metrics.revenue_growth if metrics else None,
            "dcf_discount_pct": calc_discount_pct(market.current_price if market else None, valuation.fair_value_dcf),
        }
        result = await self.provider.evaluate(payload)
        if not apply:
            return Valuation(
                isin=stock.isin,
                fundamental_score=result.fundamental_score,
                moat_score=result.moat_score,
                moat_text=result.moat_text,
                fair_value_dcf=result.fair_value_dcf,
                fair_value_nav=result.fair_value_nav,
                recommendation=result.recommendation,
                recommendation_reason=result.recommendation_reason,
                risk_notes=result.risk_notes,
                ai_cost_estimate=result.estimated_cost,
            )

        # Persist the result. When the provider had to fall back to its
        # heuristic, we mark the source as "ki_fallback" and leave the binding
        # buy/risk_buy recommendation untouched so the user is not nudged into
        # a trade based on a guess.
        source_tag = SOURCE_AI_FALLBACK if result.is_fallback else SOURCE_AI

        locks = valuation.field_locks or {}
        sources = valuation.field_sources or {}
        valuation.field_sources = sources
        valuation.field_locks = locks
        if not locks.get("fundamental_score"):
            valuation.fundamental_score = result.fundamental_score
            sources["fundamental_score"] = source_tag
        if not locks.get("moat_score"):
            valuation.moat_score = result.moat_score
            sources["moat_score"] = source_tag
        if not locks.get("moat_text"):
            valuation.moat_text = result.moat_text
            sources["moat_text"] = source_tag
        if not locks.get("fair_value_dcf"):
            valuation.fair_value_dcf = result.fair_value_dcf
            sources["fair_value_dcf"] = source_tag
        if not locks.get("fair_value_nav"):
            valuation.fair_value_nav = result.fair_value_nav
            sources["fair_value_nav"] = source_tag
        if not locks.get("recommendation"):
            if result.is_fallback:
                # Don't auto-apply a heuristic recommendation: keep whatever the
                # user (or the last real LLM call) decided. The reason field is
                # still informative, so we replace it with a clear marker.
                if not valuation.recommendation:
                    valuation.recommendation = "none"
                valuation.recommendation_reason = (
                    "Heuristischer Vorschlag – Empfehlung nicht automatisch uebernommen. "
                    + (result.recommendation_reason or "")
                ).strip()
                sources["recommendation"] = source_tag
            else:
                valuation.recommendation = result.recommendation
                valuation.recommendation_reason = result.recommendation_reason
                sources["recommendation"] = source_tag
        if not locks.get("risk_notes"):
            valuation.risk_notes = result.risk_notes
            sources["risk_notes"] = source_tag

        valuation.last_ai_at = datetime.utcnow()
        valuation.ai_cost_estimate = result.estimated_cost
        db.add(valuation)
        return valuation
