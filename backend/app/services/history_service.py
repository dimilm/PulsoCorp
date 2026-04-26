"""Hybrid price-history cache.

Strategy:
- The chart UI offers ranges 1m / 6m / 1y / 5y / max. We do not cache once
  per range; instead we cache once per *interval* (1d / 1wk / 1mo) and slice
  on read. That keeps at most 3 cached series per stock.
- Each interval has its own TTL. When the cached series is older than its
  TTL — or missing entirely — we re-fetch the maximum sensible range from
  the provider (yfinance) and replace the cache for that interval.
- All write paths are best-effort: a provider failure leaves whatever was in
  the cache and returns the stale data so the chart is never empty when we
  do have something.

This service is independent of the main refresh pipeline so a chart open
never blocks on a full-stock refresh and vice versa.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.stock import PriceHistory, Stock
from app.providers.market.base import MarketProvider

logger = logging.getLogger(__name__)


# Per-interval cache config: (yf_period, ttl_hours).
INTERVAL_CONFIG: dict[str, tuple[str, int]] = {
    "1d": ("5y", 12),
    "1wk": ("10y", 24),
    "1mo": ("max", 24 * 7),
}

# Per-range read config: (interval_to_use, days_back_or_None).
RANGE_CONFIG: dict[str, tuple[str, int | None]] = {
    "1m": ("1d", 31),
    "6m": ("1d", 186),
    "1y": ("1d", 366),
    "5y": ("1wk", 366 * 5),
    "max": ("1mo", None),
}

DEFAULT_RANGE = "1y"


class HistoryService:
    def __init__(self, provider: MarketProvider):
        self.provider = provider

    async def get_history(self, db: Session, stock: Stock, range_key: str) -> dict:
        """Return a dict with `range`, `interval`, `points` for the requested range.

        Each point has `date` (ISO yyyy-mm-dd), `open`, `high`, `low`, `close`,
        `volume`. Points are sorted by date ascending.
        """
        if range_key not in RANGE_CONFIG:
            range_key = DEFAULT_RANGE
        interval, days_back = RANGE_CONFIG[range_key]
        period, ttl_hours = INTERVAL_CONFIG[interval]

        latest_fetched = (
            db.query(func.max(PriceHistory.fetched_at))
            .filter(
                PriceHistory.isin == stock.isin,
                PriceHistory.interval == interval,
            )
            .scalar()
        )
        needs_refresh = latest_fetched is None or (
            utcnow() - latest_fetched
        ) > timedelta(hours=ttl_hours)

        if needs_refresh:
            await self._refresh_interval(db, stock, period=period, interval=interval)

        q = db.query(PriceHistory).filter(
            PriceHistory.isin == stock.isin,
            PriceHistory.interval == interval,
        )
        if days_back is not None:
            cutoff = date.today() - timedelta(days=days_back)
            q = q.filter(PriceHistory.date >= cutoff)
        rows = q.order_by(PriceHistory.date.asc()).all()

        points = [
            {
                "date": r.date.isoformat() if r.date else None,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
        return {
            "range": range_key,
            "interval": interval,
            "points": points,
            "fetched_at": latest_fetched.isoformat() if latest_fetched else None,
        }

    async def _refresh_interval(
        self, db: Session, stock: Stock, *, period: str, interval: str
    ) -> None:
        symbol = stock.ticker_override
        if not symbol:
            try:
                resolved = await self.provider.resolve_symbol(
                    isin=stock.isin,
                    name=stock.name,
                    yahoo_link=stock.link_yahoo,
                )
            except Exception as exc:
                logger.warning(
                    "Symbol resolution failed for %s while fetching history: %s",
                    stock.isin,
                    exc,
                )
                resolved = None
            symbol = resolved or stock.name
            if resolved:
                # Cache the resolved symbol on the stock so subsequent calls
                # skip the resolve roundtrip — same convention as MarketService.
                stock.ticker_override = resolved
                db.add(stock)

        try:
            points = await self.provider.fetch_history(
                symbol, period=period, interval=interval
            )
        except Exception as exc:
            logger.warning(
                "History fetch failed for %s (%s/%s): %s",
                symbol,
                period,
                interval,
                exc,
            )
            points = []

        if not points:
            # Don't wipe an existing cache just because one fetch failed —
            # better stale than empty.
            return

        db.query(PriceHistory).filter(
            PriceHistory.isin == stock.isin,
            PriceHistory.interval == interval,
        ).delete(synchronize_session=False)

        now = utcnow()
        for p in points:
            db.add(
                PriceHistory(
                    isin=stock.isin,
                    interval=interval,
                    date=p.date,
                    open=p.open,
                    high=p.high,
                    low=p.low,
                    close=p.close,
                    volume=p.volume,
                    fetched_at=now,
                )
            )
        db.commit()
