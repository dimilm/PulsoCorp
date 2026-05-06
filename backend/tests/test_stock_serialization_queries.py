"""Regression test: make sure list_stocks does not blow up into N+1 queries.

Before the eager-loading change every row in `to_stock_out` triggered four
extra `db.get` calls (market, position, metrics, similar lookups). With
`lazy="joined"` on the 1:1 children we want a near-constant query count
regardless of how many stocks we serialize.
"""
from __future__ import annotations

from sqlalchemy import event

from app.db.session import SessionLocal
from app.models.stock import MarketData, Metrics, Position, Stock
from app.services.stock_service import find_similar_stocks, list_stocks


def _seed_stocks(db, sector: str, count: int = 5) -> list[str]:
    """Insert N stocks under a unique synthetic sector for query-count tests.

    Each test passes its own sector so sibling tests cannot leak rows into
    the candidate pool used by `find_similar_stocks` and skew the count.
    """
    isins: list[str] = []
    sector_slug = "".join(ch for ch in sector if ch.isalnum())[:8].upper()
    for idx in range(count):
        isin = f"US{sector_slug:>8}{idx:02d}"[:12]
        isins.append(isin)
        db.merge(
            Stock(
                isin=isin,
                name=f"{sector} {idx}",
                sector=sector,
                currency="USD",
            )
        )
        db.merge(Position(isin=isin, tranches=idx))
        db.merge(MarketData(isin=isin, current_price=100.0 + idx, last_status="ok"))
        db.merge(Metrics(isin=isin, market_cap=1_000_000.0 * (idx + 1), analyst_target_1y=110.0))
    db.commit()
    return isins


def _count_select_statements(db) -> tuple[list[str], callable]:
    statements: list[str] = []

    def _before_cursor(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", _before_cursor)

    def _detach() -> None:
        event.remove(db.bind, "before_cursor_execute", _before_cursor)

    return statements, _detach


def test_list_stocks_does_not_n_plus_one() -> None:
    db = SessionLocal()
    try:
        sector = "QueryCounterList"
        isins = _seed_stocks(db, sector=sector, count=5)
        # Make sure cached identity-map state from seeding does not skew the
        # measurement — start each measurement with a clean session.
        db.expire_all()

        statements, detach = _count_select_statements(db)
        try:
            rows = list_stocks(db, sector=sector)
        finally:
            detach()

        assert len(rows) == len(isins)
        # With lazy="joined" we expect <= 4 SELECTs:
        # 1) the Stock query (with LEFT JOINs to market/metrics/position)
        # 2) the selectin tag fetch
        # 3) the latest-AI-run window query (single statement for all rows)
        # The threshold gives a small budget for SQLAlchemy housekeeping but
        # is far below the previous 1 + 3*N pattern.
        assert len(statements) <= 5, (
            f"Expected near-constant query count, got {len(statements)}: "
            + "\n".join(statements)
        )
    finally:
        db.close()


def test_find_similar_stocks_does_not_n_plus_one() -> None:
    db = SessionLocal()
    try:
        sector = "QueryCounterSim"
        isins = _seed_stocks(db, sector=sector, count=4)
        anchor = db.get(Stock, isins[0])
        assert anchor is not None
        db.expire_all()
        anchor = db.get(Stock, isins[0])

        statements, detach = _count_select_statements(db)
        try:
            similar = find_similar_stocks(db, anchor, limit=5)
        finally:
            detach()

        assert len(similar) == len(isins) - 1
        # Candidate fetch + tag selectin are the only expected SELECTs once
        # eager loading is in place.
        assert len(statements) <= 4, (
            f"Expected near-constant query count, got {len(statements)}: "
            + "\n".join(statements)
        )
    finally:
        db.close()
