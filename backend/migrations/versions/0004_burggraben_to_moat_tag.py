"""Replace stocks.burggraben boolean with the 'moat' tag.

Revision ID: 0004_burggraben_to_moat_tag
Revises: 0003_cascade_stock_children
Create Date: 2026-05-05

The boolean ``stocks.burggraben`` column duplicated what the tag system
already models, so we collapse it into a regular tag named ``moat``. The
upgrade migrates existing ``burggraben=1`` rows into ``stock_tags`` before
dropping the column and its index.

``batch_alter_table`` is used because SQLite does not support
``DROP COLUMN`` in place — Alembic recreates the table transparently.
``render_as_batch=True`` is already active in ``env.py`` so this works
both locally (SQLite) and in any future Postgres deployment.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_burggraben_to_moat_tag"
down_revision: Union[str, None] = "0003_cascade_stock_children"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MOAT_TAG = "moat"


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Ensure the 'moat' tag exists. INSERT OR IGNORE keeps the migration
    #    idempotent in case a tag with that name was already created manually.
    bind.execute(
        sa.text("INSERT OR IGNORE INTO tags (name) VALUES (:name)"),
        {"name": _MOAT_TAG},
    )

    # 2) Link every stock that currently has burggraben=1 to the moat tag.
    bind.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO stock_tags (isin, tag_id)
            SELECT s.isin, t.id
            FROM stocks AS s
            CROSS JOIN tags AS t
            WHERE s.burggraben = 1 AND t.name = :name
            """
        ),
        {"name": _MOAT_TAG},
    )

    # 3) Drop the now-redundant column and its index.
    with op.batch_alter_table("stocks", schema=None) as batch_op:
        batch_op.drop_index("ix_stocks_burggraben")
        batch_op.drop_column("burggraben")


def downgrade() -> None:
    # 1) Re-add the column (default false) and its index.
    with op.batch_alter_table("stocks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "burggraben",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_index("ix_stocks_burggraben", ["burggraben"])

    bind = op.get_bind()

    # 2) Restore the boolean from the moat tag membership.
    bind.execute(
        sa.text(
            """
            UPDATE stocks
            SET burggraben = 1
            WHERE isin IN (
                SELECT st.isin
                FROM stock_tags AS st
                JOIN tags AS t ON t.id = st.tag_id
                WHERE t.name = :name
            )
            """
        ),
        {"name": _MOAT_TAG},
    )

    # 3) Remove the moat tag links and the tag itself so the schema state
    #    matches what existed before the original upgrade ran.
    bind.execute(
        sa.text(
            """
            DELETE FROM stock_tags
            WHERE tag_id IN (SELECT id FROM tags WHERE name = :name)
            """
        ),
        {"name": _MOAT_TAG},
    )
    bind.execute(
        sa.text("DELETE FROM tags WHERE name = :name"),
        {"name": _MOAT_TAG},
    )
