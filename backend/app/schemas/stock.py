from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


Recommendation = Literal["none", "buy", "risk_buy"]


class StockBase(BaseModel):
    isin: str = Field(min_length=12, max_length=12)
    name: str
    sector: str | None = None
    currency: str | None = None
    burggraben: bool = False
    reasoning: str | None = None
    ticker_override: str | None = None
    link_yahoo: str | None = None
    link_finanzen: str | None = None
    link_onvista_chart: str | None = None
    link_onvista_fundamental: str | None = None
    tranches: int = 0
    tags: list[str] = Field(default_factory=list)


class StockCreate(StockBase):
    pass


class StockUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None
    currency: str | None = None
    burggraben: bool | None = None
    reasoning: str | None = None
    ticker_override: str | None = None
    tranches: int | None = None
    tags: list[str] | None = None
    recommendation: Recommendation | None = None
    recommendation_reason: str | None = None
    fundamental_score: int | None = None
    moat_score: int | None = None
    fair_value_dcf: float | None = None
    fair_value_nav: float | None = None


class StockOut(StockBase):
    current_price: float | None = None
    day_change_pct: float | None = None
    last_updated: datetime | None = None
    last_status: str | None = None
    recommendation: Recommendation | None = "none"
    dcf_discount_pct: float | None = None
    nav_discount_pct: float | None = None
    analyst_target_distance_pct: float | None = None
    invested_capital_eur: float = 0
    fundamental_score: int | None = None
    moat_score: int | None = None
    pe_forward: float | None = None
    pe_min_5y: float | None = None
    pe_max_5y: float | None = None
    pe_avg_5y: float | None = None
    dividend_yield_current: float | None = None
    dividend_yield_avg_5y: float | None = None
    analyst_target_1y: float | None = None
    market_cap: float | None = None
    equity_ratio: float | None = None
    debt_ratio: float | None = None
    revenue_growth: float | None = None
    missing_metrics: list[str] = Field(default_factory=list)
    field_sources: dict = Field(default_factory=dict)
    field_locks: dict = Field(default_factory=dict)


class LockRequest(BaseModel):
    field_names: list[str]
    locked: bool = True
