"""Regression test: raw-SQL DELETE FROM stocks cascades to child tables.

`MarketData`, `Metrics`, and `Position` all have ON DELETE CASCADE on their
FK to `stocks`. This test bypasses the ORM (which would handle cascade via
its own mechanism) to prove the *database-level* constraint is in place after
migration 0003_cascade_stock_children.

SQLite does not enforce FK constraints by default; we enable them per
connection with ``PRAGMA foreign_keys = ON`` for this test.
"""
from __future__ import annotations

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.stock import MarketData, Metrics, Position, Stock


_ISIN = "US0CASCADE0001"


def _seed(db) -> None:
    db.merge(Stock(isin=_ISIN, name="CascadeTest", currency="USD"))
    db.merge(Position(isin=_ISIN, tranches=2))
    db.merge(MarketData(isin=_ISIN, current_price=42.0, last_status="ok"))
    db.merge(Metrics(isin=_ISIN, market_cap=1_000_000.0))
    db.commit()


def _cleanup(db) -> None:
    db.execute(text("DELETE FROM market_data WHERE isin = :i"), {"i": _ISIN})
    db.execute(text("DELETE FROM metrics WHERE isin = :i"), {"i": _ISIN})
    db.execute(text("DELETE FROM positions WHERE isin = :i"), {"i": _ISIN})
    db.execute(text("DELETE FROM stocks WHERE isin = :i"), {"i": _ISIN})
    db.commit()


def test_raw_delete_cascades_to_child_tables():
    """Deleting a stock via raw SQL removes market_data/metrics/positions."""
    db = SessionLocal()
    try:
        _seed(db)

        # Enable SQLite FK enforcement for this connection.
        db.execute(text("PRAGMA foreign_keys = ON"))

        # Verify children exist before the delete.
        assert db.get(MarketData, _ISIN) is not None
        assert db.get(Metrics, _ISIN) is not None
        assert db.get(Position, _ISIN) is not None

        # Raw DELETE — bypasses the ORM's cascade="all,delete-orphan" logic.
        db.execute(text("DELETE FROM stocks WHERE isin = :i"), {"i": _ISIN})
        db.commit()

        # Children must be gone due to DB-level CASCADE.
        db.expire_all()
        assert db.get(MarketData, _ISIN) is None, "market_data not cascaded"
        assert db.get(Metrics, _ISIN) is None, "metrics not cascaded"
        assert db.get(Position, _ISIN) is None, "positions not cascaded"
    finally:
        # Best-effort cleanup in case the test failed before the DELETE.
        try:
            _cleanup(db)
        except Exception:
            db.rollback()
        db.close()
