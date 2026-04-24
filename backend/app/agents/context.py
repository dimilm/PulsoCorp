"""Shared helpers to assemble the per-stock context dict that agents consume.

Centralising this avoids duplicating field plumbing across every agent and
guarantees that all agents see the same numeric values (so users can compare
runs side by side).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.stock import MarketData, Metrics, Stock


def build_stock_context(db: Session, stock: Stock) -> dict[str, Any]:
    market = db.get(MarketData, stock.isin)
    metrics = db.get(Metrics, stock.isin)
    return {
        "isin": stock.isin,
        "name": stock.name,
        "sector": stock.sector,
        "currency": stock.currency,
        "burggraben": bool(stock.burggraben),
        "reasoning": stock.reasoning,
        "current_price": market.current_price if market else None,
        "day_change_pct": market.day_change_pct if market else None,
        "metrics": {
            "pe_forward": metrics.pe_forward if metrics else None,
            "pe_avg_5y": metrics.pe_avg_5y if metrics else None,
            "pe_min_5y": metrics.pe_min_5y if metrics else None,
            "pe_max_5y": metrics.pe_max_5y if metrics else None,
            "dividend_yield_current": metrics.dividend_yield_current if metrics else None,
            "dividend_yield_avg_5y": metrics.dividend_yield_avg_5y if metrics else None,
            "analyst_target_1y": metrics.analyst_target_1y if metrics else None,
            "market_cap": metrics.market_cap if metrics else None,
            "equity_ratio": metrics.equity_ratio if metrics else None,
            "debt_ratio": metrics.debt_ratio if metrics else None,
            "revenue_growth": metrics.revenue_growth if metrics else None,
        },
    }
