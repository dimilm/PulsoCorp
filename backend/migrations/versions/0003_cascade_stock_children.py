"""Add ON DELETE CASCADE to market_data, metrics and positions FK to stocks.

Revision ID: 0003_cascade_stock_children
Revises: 0002_job_sources
Create Date: 2026-05-03

Previously the FKs on these three tables had no ``ondelete`` clause, so a
raw-SQL ``DELETE FROM stocks`` would leave orphaned rows behind. The ORM
cascade (``cascade="all,delete-orphan"``) still cleaned up when going through
SQLAlchemy, but the DB-level guard was missing.

``batch_alter_table`` is used because SQLite does not support in-place ALTER
COLUMN — it recreates the table transparently. ``render_as_batch=True`` is
already active in ``env.py`` so this works both locally (SQLite) and in any
future Postgres deployment.

The existing FKs were created without explicit names (SQLite stores them as
``name=None``). We pass ``naming_convention`` to ``batch_alter_table`` so
Alembic assigns a deterministic name to the reflected unnamed FK, which makes
the ``drop_constraint`` call possible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0003_cascade_stock_children"
down_revision: Union[str, None] = "0002_job_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHILD_TABLES = ("market_data", "metrics", "positions")

# Applied to the reflected MetaData so Alembic can auto-name the unnamed
# FK constraints that SQLite stores without names.
_NAMING_CONVENTION: dict = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def _fk_name(table: str) -> str:
    return f"fk_{table}_isin_stocks"


def upgrade() -> None:
    for table in _CHILD_TABLES:
        fk = _fk_name(table)
        with op.batch_alter_table(
            table,
            schema=None,
            naming_convention=_NAMING_CONVENTION,
        ) as batch_op:
            batch_op.drop_constraint(fk, type_="foreignkey")
            batch_op.create_foreign_key(
                fk,
                "stocks",
                ["isin"],
                ["isin"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    for table in reversed(_CHILD_TABLES):
        fk = _fk_name(table)
        with op.batch_alter_table(
            table,
            schema=None,
            naming_convention=_NAMING_CONVENTION,
        ) as batch_op:
            batch_op.drop_constraint(fk, type_="foreignkey")
            batch_op.create_foreign_key(
                None,
                "stocks",
                ["isin"],
                ["isin"],
            )
