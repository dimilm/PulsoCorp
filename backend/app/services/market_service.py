from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.stock import MarketData, Metrics, Stock
from app.providers.market.base import MarketProvider, MetricsData, QuoteData


class MarketService:
    def __init__(self, provider: MarketProvider):
        self.provider = provider

    async def resolve_symbol(self, stock: Stock) -> str:
        """Resolve and remember the provider symbol for a stock.

        Returns the symbol that was used (cached override, provider lookup, or
        finally the stock name as last-resort fallback).
        """
        if stock.ticker_override:
            return stock.ticker_override
        provider_symbol = await self.provider.resolve_symbol(
            isin=stock.isin,
            name=stock.name,
            yahoo_link=stock.link_yahoo,
        )
        if provider_symbol:
            stock.ticker_override = provider_symbol
            return provider_symbol
        return stock.name

    async def fetch_quote(self, symbol: str) -> QuoteData:
        return await self.provider.fetch_quote(symbol)

    async def fetch_metrics(self, symbol: str) -> MetricsData:
        return await self.provider.fetch_metrics(symbol)

    def persist(
        self,
        db: Session,
        stock: Stock,
        quote: QuoteData,
        metrics: MetricsData,
    ) -> None:
        row = db.get(MarketData, stock.isin) or MarketData(isin=stock.isin)
        row.current_price = quote.current_price
        row.day_change_pct = quote.day_change_pct
        row.last_updated = utcnow()
        row.last_status = "ok"
        row.last_error = None
        db.add(row)

        if quote.currency and not stock.currency:
            stock.currency = quote.currency

        m = db.get(Metrics, stock.isin) or Metrics(isin=stock.isin)
        m.pe_forward = metrics.pe_forward
        m.pe_min_5y = metrics.pe_min_5y
        m.pe_max_5y = metrics.pe_max_5y
        m.pe_avg_5y = metrics.pe_avg_5y
        m.dividend_yield_current = metrics.dividend_yield_current
        m.dividend_yield_avg_5y = metrics.dividend_yield_avg_5y
        m.analyst_target_1y = metrics.analyst_target_1y
        m.market_cap = metrics.market_cap
        m.equity_ratio = metrics.equity_ratio
        m.debt_ratio = metrics.debt_ratio
        m.revenue_growth = metrics.revenue_growth
        db.add(m)
        db.add(stock)

    async def refresh_stock(self, db: Session, stock: Stock) -> None:
        """Convenience full-refresh for the single-stock endpoint."""
        symbol = await self.resolve_symbol(stock)
        quote = await self.fetch_quote(symbol)
        metrics = await self.fetch_metrics(symbol)
        self.persist(db, stock, quote, metrics)
