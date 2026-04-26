"""Unit tests for `YFinanceProvider._fetch_balance_sheet_values`.

We cannot hit yfinance/Yahoo from CI, so we patch the `balance_sheet` /
`quarterly_balance_sheet` accessors with hand-crafted pandas DataFrames
that mirror the shape Yahoo returns (rows = line items, columns = report
dates with the most recent in column 0).
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, PropertyMock

import pandas as pd

from app.providers.market.yfinance_provider import YFinanceProvider


def _make_balance_sheet(rows: dict[str, list[float | None]], cols: list[str]) -> pd.DataFrame:
    """Build a balance-sheet DataFrame mirroring yfinance's shape.

    yfinance returns a frame with row index = line item (e.g. "Total Assets")
    and columns = report dates with the most recent date in column 0.
    `pd.DataFrame(rows, index=cols)` builds the transpose of that, so we
    transpose once to land on the correct orientation.
    """
    return pd.DataFrame(rows, index=cols).T


def _fake_ticker(*, balance_sheet=None, quarterly_balance_sheet=None) -> MagicMock:
    """yf.Ticker exposes balance_sheet/quarterly_balance_sheet as properties.

    Using `PropertyMock` mirrors the real attribute access behaviour and makes
    sure the helper's `getattr(ticker, accessor)` path still works.
    """
    ticker = MagicMock(spec=["balance_sheet", "quarterly_balance_sheet", "ticker"])
    type(ticker).balance_sheet = PropertyMock(return_value=balance_sheet)
    type(ticker).quarterly_balance_sheet = PropertyMock(return_value=quarterly_balance_sheet)
    ticker.ticker = "FAKE"
    return ticker


def test_balance_sheet_returns_latest_annual_values() -> None:
    cols = ["2024-12-31", "2023-12-31"]
    annual = _make_balance_sheet(
        {
            "Total Assets": [1_000.0, 900.0],
            "Stockholders Equity": [400.0, 350.0],
            "Total Debt": [200.0, 250.0],
        },
        cols,
    )
    ticker = _fake_ticker(balance_sheet=annual)
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert assets == 1_000.0
    assert equity == 400.0
    assert debt == 200.0


def test_balance_sheet_falls_back_to_quarterly_when_annual_empty() -> None:
    quarterly = _make_balance_sheet(
        {
            "Total Assets": [800.0],
            "Common Stock Equity": [320.0],
            "Total Debt": [180.0],
        },
        ["2025-03-31"],
    )
    ticker = _fake_ticker(
        balance_sheet=pd.DataFrame(),
        quarterly_balance_sheet=quarterly,
    )
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert assets == 800.0
    assert equity == 320.0  # picked up via "Common Stock Equity" alias
    assert debt == 180.0


def test_balance_sheet_returns_none_when_both_accessors_empty() -> None:
    ticker = _fake_ticker(
        balance_sheet=pd.DataFrame(),
        quarterly_balance_sheet=pd.DataFrame(),
    )
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert (assets, equity, debt) == (None, None, None)


def test_balance_sheet_skips_nan_in_latest_column() -> None:
    """If the newest column has NaN for a row, fall through to older periods."""
    cols = ["2024-12-31", "2023-12-31"]
    annual = _make_balance_sheet(
        {
            "Total Assets": [float("nan"), 950.0],
            "Stockholders Equity": [float("nan"), 410.0],
            "Total Debt": [float("nan"), 220.0],
        },
        cols,
    )
    ticker = _fake_ticker(balance_sheet=annual)
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert assets == 950.0
    assert equity == 410.0
    assert debt == 220.0


def test_balance_sheet_partial_rows_are_returned() -> None:
    """Only equity present → assets/debt come back as None, equity wins."""
    annual = _make_balance_sheet(
        {"Total Equity Gross Minority Interest": [500.0]},
        ["2024-12-31"],
    )
    ticker = _fake_ticker(balance_sheet=annual)
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert assets is None
    assert equity == 500.0
    assert debt is None


def test_balance_sheet_handles_accessor_exception() -> None:
    """A raising accessor must not crash — we just log and try the next one."""
    ticker = MagicMock(spec=["balance_sheet", "quarterly_balance_sheet", "ticker"])
    type(ticker).balance_sheet = PropertyMock(side_effect=RuntimeError("boom"))
    quarterly = _make_balance_sheet(
        {
            "Total Assets": [700.0],
            "Stockholders Equity": [300.0],
            "Total Debt": [150.0],
        },
        ["2025-03-31"],
    )
    type(ticker).quarterly_balance_sheet = PropertyMock(return_value=quarterly)
    ticker.ticker = "FAKE"
    provider = YFinanceProvider()

    assets, equity, debt = asyncio.run(provider._fetch_balance_sheet_values(ticker))
    assert (assets, equity, debt) == (700.0, 300.0, 150.0)
