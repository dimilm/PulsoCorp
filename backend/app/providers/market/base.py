from dataclasses import dataclass
from datetime import date


@dataclass
class QuoteData:
    current_price: float | None
    day_change_pct: float | None
    currency: str | None


@dataclass
class MetricsData:
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


@dataclass
class OHLCPoint:
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


class MarketProvider:
    async def resolve_symbol(self, *, isin: str, name: str | None = None, yahoo_link: str | None = None) -> str | None:
        return None

    async def fetch_quote(self, symbol: str) -> QuoteData:
        raise NotImplementedError

    async def fetch_metrics(self, symbol: str) -> MetricsData:
        raise NotImplementedError

    async def fetch_history(self, symbol: str, *, period: str, interval: str) -> list[OHLCPoint]:
        raise NotImplementedError
