from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qs, urlparse

import yfinance as yf

from app.providers.market.base import MarketProvider, MetricsData, OHLCPoint, QuoteData

logger = logging.getLogger(__name__)


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
        except Exception as exc:
            logger.warning("yfinance ISIN lookup failed for %s: %s", isin, exc)
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

    async def fetch_history(self, symbol: str, *, period: str, interval: str) -> list[OHLCPoint]:
        """Return OHLC bars for the requested period/interval as plain dataclasses.

        Empty list on any failure — callers must treat history as best-effort
        because yfinance occasionally rate-limits or returns gaps. We strip
        timezone info so downstream comparisons stay simple.
        """
        ticker = await asyncio.to_thread(yf.Ticker, symbol)
        try:
            hist = await asyncio.to_thread(
                lambda: ticker.history(period=period, interval=interval, auto_adjust=False)
            )
        except Exception as exc:
            logger.warning(
                "yfinance history fetch failed for %s (%s/%s): %s",
                symbol,
                period,
                interval,
                exc,
            )
            return []
        if hist is None or getattr(hist, "empty", True):
            return []

        points: list[OHLCPoint] = []
        for ts, row in hist.iterrows():
            ts_naive = _to_naive(ts)
            d = ts_naive.date() if hasattr(ts_naive, "date") else ts_naive
            points.append(
                OHLCPoint(
                    date=d,
                    open=_safe_float(row.get("Open") if hasattr(row, "get") else row["Open"]),
                    high=_safe_float(row.get("High") if hasattr(row, "get") else row["High"]),
                    low=_safe_float(row.get("Low") if hasattr(row, "get") else row["Low"]),
                    close=_safe_float(row.get("Close") if hasattr(row, "get") else row["Close"]),
                    volume=_safe_int(row.get("Volume") if hasattr(row, "get") else row["Volume"]),
                )
            )
        return points

    async def fetch_metrics(self, symbol: str) -> MetricsData:
        ticker = await asyncio.to_thread(yf.Ticker, symbol)
        info = await asyncio.to_thread(lambda: ticker.info)
        # Try to derive a real 5y PE band from monthly close prices and the
        # trailing EPS trajectory. yfinance does not expose a clean PE history,
        # so we rebuild it from price / EPS samples. If anything is missing we
        # return None instead of leaking a price-as-PE approximation.
        pe_min, pe_max, pe_avg = await self._fetch_pe_band(ticker, info)
        # yfinance hat `totalAssets` / `totalStockholderEquity` aus dem
        # `info`-Dict effektiv entfernt — nur `totalDebt` taucht dort noch
        # zuverlässig auf. Echte Bilanzpositionen kommen jetzt aus
        # `ticker.balance_sheet` (annual, Fallback: quarterly).
        total_assets, total_equity, total_debt = await self._fetch_balance_sheet_values(ticker)
        if total_debt is None:
            total_debt = _safe_float(info.get("totalDebt"))
        equity_ratio = (total_equity / total_assets * 100) if total_assets and total_equity else None
        debt_ratio = (total_debt / total_equity * 100) if total_debt and total_equity else None
        return MetricsData(
            pe_forward=info.get("forwardPE"),
            pe_min_5y=pe_min,
            pe_max_5y=pe_max,
            pe_avg_5y=pe_avg,
            # yfinance liefert `dividendYield` seit ~v0.2.40 bereits als Prozent
            # (0.91 = 0,91 %), nicht mehr als Bruch. Direkt übernehmen, sonst
            # erscheinen Renditen 100x zu hoch in der UI. `fiveYearAvgDividendYield`
            # war schon immer Prozent.
            dividend_yield_current=info.get("dividendYield"),
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
        except Exception as exc:
            logger.warning(
                "yfinance PE-band history fetch failed for %s: %s",
                getattr(ticker, "ticker", "?"),
                exc,
            )
            return None, None, None
        if hist is None or "Close" not in hist or hist["Close"].dropna().empty:
            return None, None, None

        # Build a (date -> trailing diluted EPS) series. We try the new
        # `income_stmt` accessor (annual) first and fall back to quarterly.
        eps_series: list[tuple[object, float]] = []
        for accessor, scale in (("quarterly_income_stmt", 4), ("income_stmt", 1)):
            try:
                stmt = await asyncio.to_thread(lambda a=accessor: getattr(ticker, a))
            except Exception as exc:
                logger.warning(
                    "yfinance income-statement accessor %s failed for %s: %s",
                    accessor,
                    getattr(ticker, "ticker", "?"),
                    exc,
                )
                stmt = None
            if stmt is None or getattr(stmt, "empty", True):
                continue
            for row_label in ("Diluted EPS", "Basic EPS"):
                if row_label in stmt.index:
                    series = stmt.loc[row_label].dropna()
                    eps_series = [
                        (_to_naive(idx), float(val) * (scale if scale else 1))
                        for idx, val in series.items()
                    ]
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
            # yfinance returns tz-aware timestamps for `history`, but EPS
            # statements ship tz-naive — strip tz on both sides to compare.
            ts_naive = _to_naive(ts)
            applicable = [
                eps for eps_ts, eps in eps_sorted if eps_ts <= ts_naive and eps not in (0, None)
            ]
            if not applicable:
                continue
            pes.append(float(close) / applicable[-1])
        if not pes:
            return None, None, None
        return min(pes), max(pes), sum(pes) / len(pes)

    async def _fetch_balance_sheet_values(
        self, ticker: "yf.Ticker"
    ) -> tuple[float | None, float | None, float | None]:
        """Pull (total_assets, total_equity, total_debt) from the latest balance sheet.

        Yahoo's quote summary (`Ticker.info`) no longer exposes assets/equity
        for most tickers. The balance-sheet DataFrame is the only reliable
        source. Row labels differ across yfinance/Yahoo versions, so we try
        a small list of known synonyms. Annual data is preferred; if it is
        empty (some companies skip annual filings) we fall back to quarterly.
        Any failure returns the partial result we managed to extract.
        """
        # Newest period sits in column 0 in yfinance balance sheets.
        equity_labels = (
            "Stockholders Equity",
            "Total Stockholder Equity",
            "Common Stock Equity",
            "Total Equity Gross Minority Interest",
        )
        debt_labels = ("Total Debt", "Long Term Debt")
        assets_labels = ("Total Assets",)

        for accessor in ("balance_sheet", "quarterly_balance_sheet"):
            try:
                bs = await asyncio.to_thread(lambda a=accessor: getattr(ticker, a))
            except Exception as exc:
                logger.warning(
                    "yfinance balance-sheet accessor %s failed for %s: %s",
                    accessor,
                    getattr(ticker, "ticker", "?"),
                    exc,
                )
                continue
            if bs is None or getattr(bs, "empty", True):
                continue

            def _latest(row_names: tuple[str, ...]) -> float | None:
                for name in row_names:
                    if name in bs.index:
                        series = bs.loc[name].dropna()
                        if not series.empty:
                            return _safe_float(series.iloc[0])
                return None

            assets = _latest(assets_labels)
            equity = _latest(equity_labels)
            debt = _latest(debt_labels)
            if assets is not None or equity is not None or debt is not None:
                return assets, equity, debt
        return None, None, None


def _to_naive(value):
    """Drop timezone info so tz-aware and tz-naive timestamps can be compared."""
    if getattr(value, "tzinfo", None) is None:
        return value
    tz_localize = getattr(value, "tz_localize", None)
    if callable(tz_localize):
        try:
            return tz_localize(None)
        except (TypeError, ValueError):
            pass
    try:
        return value.replace(tzinfo=None)
    except (TypeError, AttributeError):
        return value


def _safe_float(value) -> float | None:
    """Convert pandas/numpy scalars to plain float, treating NaN as None."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check without importing math
        return None
    return f


def _safe_int(value) -> int | None:
    f = _safe_float(value)
    if f is None:
        return None
    return int(f)
