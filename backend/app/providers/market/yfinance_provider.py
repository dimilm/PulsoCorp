from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

import yfinance as yf

from app.providers.market.base import MarketProvider, MetricsData, QuoteData


class YFinanceProvider(MarketProvider):
    async def resolve_symbol(self, *, isin: str, name: str | None = None, yahoo_link: str | None = None) -> str | None:
        if yahoo_link:
            parsed = urlparse(yahoo_link)
            parts = [p for p in parsed.path.split("/") if p]
            if "quote" in parts:
                idx = parts.index("quote")
                if idx + 1 < len(parts):
                    return parts[idx + 1].upper()
            query_symbol = parse_qs(parsed.query).get("p", [None])[0]
            if query_symbol:
                return query_symbol.upper()
        try:
            search = await asyncio.to_thread(lambda: yf.Search(isin, max_results=1))
            quotes = getattr(search, "quotes", []) or []
            if quotes:
                symbol = quotes[0].get("symbol")
                if symbol:
                    return str(symbol).upper()
        except Exception:
            return None
        return None

    async def fetch_quote(self, symbol: str) -> QuoteData:
        info = await asyncio.to_thread(lambda: yf.Ticker(symbol).info)
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose")
        change_pct = None
        if current and prev_close:
            change_pct = ((current - prev_close) / prev_close) * 100
        return QuoteData(current_price=current, day_change_pct=change_pct, currency=info.get("currency"))

    async def fetch_metrics(self, symbol: str) -> MetricsData:
        ticker = await asyncio.to_thread(yf.Ticker, symbol)
        info = await asyncio.to_thread(lambda: ticker.info)
        # Try to derive a real 5y PE band from monthly close prices and the
        # trailing EPS trajectory. yfinance does not expose a clean PE history,
        # so we rebuild it from price / EPS samples. If anything is missing we
        # return None instead of leaking a price-as-PE approximation.
        pe_min, pe_max, pe_avg = await self._fetch_pe_band(ticker, info)
        total_assets = info.get("totalAssets")
        total_equity = info.get("totalStockholderEquity")
        total_debt = info.get("totalDebt")
        equity_ratio = (total_equity / total_assets * 100) if total_assets and total_equity else None
        debt_ratio = (total_debt / total_equity * 100) if total_debt and total_equity else None
        return MetricsData(
            pe_forward=info.get("forwardPE"),
            pe_min_5y=pe_min,
            pe_max_5y=pe_max,
            pe_avg_5y=pe_avg,
            dividend_yield_current=(info.get("dividendYield") or 0) * 100 if info.get("dividendYield") else None,
            dividend_yield_avg_5y=info.get("fiveYearAvgDividendYield"),
            analyst_target_1y=info.get("targetMedianPrice"),
            market_cap=info.get("marketCap"),
            equity_ratio=equity_ratio,
            debt_ratio=debt_ratio,
            revenue_growth=(info.get("revenueGrowth") or 0) * 100 if info.get("revenueGrowth") else None,
        )

    async def _fetch_pe_band(
        self, ticker: "yf.Ticker", info: dict
    ) -> tuple[float | None, float | None, float | None]:
        """Reconstruct a 5y PE min/max/avg from monthly closes and EPS history.

        Returns (None, None, None) when the inputs are insufficient. We
        deliberately avoid the old approximation that used the close price as
        the PE value because it produced misleading numbers in the UI.
        """
        try:
            hist = await asyncio.to_thread(
                lambda: ticker.history(period="5y", interval="1mo", auto_adjust=False)
            )
        except Exception:
            return None, None, None
        if hist is None or "Close" not in hist or hist["Close"].dropna().empty:
            return None, None, None

        # Build a (date -> trailing diluted EPS) series. We try the new
        # `income_stmt` accessor (annual) first and fall back to quarterly.
        eps_series: list[tuple[object, float]] = []
        for accessor, scale in (("quarterly_income_stmt", 4), ("income_stmt", 1)):
            try:
                stmt = await asyncio.to_thread(lambda a=accessor: getattr(ticker, a))
            except Exception:
                stmt = None
            if stmt is None or getattr(stmt, "empty", True):
                continue
            for row_label in ("Diluted EPS", "Basic EPS"):
                if row_label in stmt.index:
                    series = stmt.loc[row_label].dropna()
                    eps_series = [(idx, float(val) * (scale if scale else 1)) for idx, val in series.items()]
                    break
            if eps_series:
                break
        if not eps_series:
            # As a last resort, take current trailing EPS and apply it across
            # the full window. This keeps min/max meaningful (purely price
            # driven) while still flagging the limitation in the moat_text.
            trailing_eps = info.get("trailingEps")
            if not trailing_eps:
                return None, None, None
            closes = [float(v) for v in hist["Close"].dropna().tolist()]
            pes = [c / trailing_eps for c in closes if trailing_eps]
            if not pes:
                return None, None, None
            return min(pes), max(pes), sum(pes) / len(pes)

        eps_sorted = sorted(eps_series, key=lambda item: item[0])
        pes: list[float] = []
        for ts, close in hist["Close"].dropna().items():
            applicable = [eps for eps_ts, eps in eps_sorted if eps_ts <= ts and eps not in (0, None)]
            if not applicable:
                continue
            pes.append(float(close) / applicable[-1])
        if not pes:
            return None, None, None
        return min(pes), max(pes), sum(pes) / len(pes)
