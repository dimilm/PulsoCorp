"""URL validation on the Stock create/update schemas.

We tightened the `link_*` fields after the audit: empty strings collapse
to `None` (so the legacy CSV import + blank UI inputs continue to work)
but malformed values are rejected before they hit the database. This
test pins down both halves of that contract.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.stock import StockCreate, StockUpdate


def _base_payload(**overrides: object) -> dict:
    payload = {
        "isin": "US0378331005",
        "name": "Apple Inc.",
        "sector": "Tech",
        "currency": "USD",
        "tranches": 0,
        "tags": [],
    }
    payload.update(overrides)
    return payload


def test_create_accepts_valid_https_link() -> None:
    stock = StockCreate(**_base_payload(link_yahoo="https://finance.yahoo.com/quote/AAPL"))
    assert stock.link_yahoo == "https://finance.yahoo.com/quote/AAPL"


def test_create_collapses_empty_link_to_none() -> None:
    stock = StockCreate(**_base_payload(link_finanzen=""))
    assert stock.link_finanzen is None


def test_create_strips_whitespace_only_link_to_none() -> None:
    stock = StockCreate(**_base_payload(link_onvista_chart="   "))
    assert stock.link_onvista_chart is None


def test_create_rejects_non_http_link() -> None:
    with pytest.raises(ValidationError) as exc:
        StockCreate(**_base_payload(link_yahoo="javascript:alert(1)"))
    assert "http://" in str(exc.value)


def test_update_validates_links_too() -> None:
    with pytest.raises(ValidationError):
        StockUpdate(link_finanzen="not-a-url")
    cleared = StockUpdate(link_finanzen="")
    assert cleared.link_finanzen is None
