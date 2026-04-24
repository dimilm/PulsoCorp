"""Add helpful query indexes.

Revision ID: 0002_add_indexes
Revises: 0001_initial
Create Date: 2026-04-23

The watchlist filters and the runs page do a lot of scans against columns that
were not indexed in the initial schema. With ~hundreds of stocks this is
fine, but the indexes are cheap and pay off as soon as the dataset grows.

We use `IF NOT EXISTS` semantics by issuing the operations inside a small
helper so re-running the migration on a partially-indexed DB stays safe.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_add_indexes"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (index_name, table_name, [columns], unique?)
_INDEXES: list[tuple[str, str, list[str], bool]] = [
    ("ix_stocks_sector", "stocks", ["sector"], False),
    ("ix_stocks_burggraben", "stocks", ["burggraben"], False),
    ("ix_stocks_name", "stocks", ["name"], False),
    ("ix_valuations_recommendation", "valuations", ["recommendation"], False),
    ("ix_valuations_fundamental_score", "valuations", ["fundamental_score"], False),
    ("ix_market_data_last_status", "market_data", ["last_status"], False),
    ("ix_market_data_last_updated", "market_data", ["last_updated"], False),
    ("ix_run_logs_phase", "run_logs", ["phase"], False),
    ("ix_run_logs_started_at", "run_logs", ["started_at"], False),
    ("ix_stock_tags_tag_id", "stock_tags", ["tag_id"], False),
]


def _existing_indexes(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {ix["name"] for ix in inspector.get_indexes(table)}


def upgrade() -> None:
    by_table: dict[str, set[str]] = {}
    for name, table, columns, unique in _INDEXES:
        existing = by_table.setdefault(table, _existing_indexes(table))
        if name in existing:
            continue
        op.create_index(name, table, columns, unique=unique)
        existing.add(name)


def downgrade() -> None:
    for name, table, _columns, _unique in reversed(_INDEXES):
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            # The index may already be gone if it was never created (e.g. a
            # partial upgrade). Downgrade should stay idempotent.
            pass
