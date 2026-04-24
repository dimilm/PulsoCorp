"""Add price_history cache table.

Revision ID: 0003_add_price_history
Revises: 0002_add_indexes
Create Date: 2026-04-24

The table caches OHLC bars per (isin, interval, date) so the stock detail
chart can serve repeat requests from the DB without round-tripping yfinance
every time. Filling and TTL-refreshing happens in `history_service`; this
migration is purely additive — no backfill, no data migration.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_add_price_history"
down_revision: Union[str, None] = "0002_add_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column(
            "isin",
            sa.String(12),
            sa.ForeignKey("stocks.isin", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("interval", sa.String(8), primary_key=True),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_price_history_isin_interval",
        "price_history",
        ["isin", "interval"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_isin_interval", table_name="price_history")
    op.drop_table("price_history")
