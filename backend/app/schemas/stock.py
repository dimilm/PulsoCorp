from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Names of every link_* field on stock-shaped schemas. Centralised here so
# StockBase and StockUpdate stay in sync — both schemas wire the validator
# to this exact list.
_URL_FIELDS = (
    "link_yahoo",
    "link_finanzen",
    "link_onvista_chart",
    "link_onvista_fundamental",
)


def _normalize_url(value: str | None) -> str | None:
    """Validate the optional URL fields on the stock schemas.

    The legacy CSV import produces empty strings for missing links and the
    UI sends back blank inputs the same way, so we coerce those to `None`
    instead of forcing the user to clear the field manually. When a value
    is present we require an `http://` or `https://` prefix so a malformed
    paste cannot end up persisted (and later rendered as a "click" target
    that opens a relative path inside our own app).
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        raise ValueError("Link must start with http:// or https://")
    return stripped


class StockBase(BaseModel):
    isin: str = Field(min_length=12, max_length=12)
    name: str
    sector: str | None = None
    currency: str | None = None
    reasoning: str | None = None
    ticker_override: str | None = None
    link_yahoo: str | None = None
    link_finanzen: str | None = None
    link_onvista_chart: str | None = None
    link_onvista_fundamental: str | None = None
    tranches: int = 0
    tags: list[str] = Field(default_factory=list)

    @field_validator(*_URL_FIELDS, mode="before")
    @classmethod
    def _validate_links(cls, value: str | None) -> str | None:
        return _normalize_url(value)


class StockCreate(StockBase):
    pass


class StockUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None
    currency: str | None = None
    reasoning: str | None = None
    ticker_override: str | None = None
    link_yahoo: str | None = None
    link_finanzen: str | None = None
    link_onvista_chart: str | None = None
    link_onvista_fundamental: str | None = None
    tranches: int | None = None
    tags: list[str] | None = None

    @field_validator(*_URL_FIELDS, mode="before")
    @classmethod
    def _validate_links(cls, value: str | None) -> str | None:
        return _normalize_url(value)


class AILatestRun(BaseModel):
    """Compact projection of the most recent successful AI run for a stock.

    Only the fields the watchlist pills need are exposed via `summary`; the
    full run remains available through `/api/v1/ai/runs/{run_id}`.
    """

    agent_id: str
    created_at: datetime
    model: str
    summary: dict[str, Any]


class StockOut(StockBase):
    current_price: float | None = None
    day_change_pct: float | None = None
    last_updated: datetime | None = None
    last_status: str | None = None
    analyst_target_distance_pct: float | None = None
    invested_capital_eur: float = 0
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
    latest_ai_runs: dict[str, AILatestRun] = Field(default_factory=dict)


class SectorSuggestion(BaseModel):
    name: str
    count: int


class HistoryPoint(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None


class HistoryResponse(BaseModel):
    isin: str
    range: str
    interval: str
    points: list[HistoryPoint]
    fetched_at: str | None = None
