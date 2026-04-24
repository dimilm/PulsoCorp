"""Replace single AI agent with the multi-agent system.

Revision ID: 0004_ai_agents
Revises: 0003_add_price_history
Create Date: 2026-04-24

The application is not in production yet, so no data migration is required.
This revision:

* drops the ``valuations`` table (including the legacy ``recommendation`` enum)
* drops the four ``ai_*`` columns from ``run_stock_status`` because the refresh
  pipeline no longer triggers an AI step
* creates the new ``ai_runs`` history table consumed by the AI agents panel
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0004_ai_agents"
down_revision: Union[str, None] = "0003_add_price_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("valuations")
    sa.Enum(name="recommendation").drop(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("run_stock_status") as batch:
        batch.drop_column("ai_status")
        batch.drop_column("ai_started_at")
        batch.drop_column("ai_finished_at")
        batch.drop_column("ai_error")

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "isin",
            sa.String(12),
            sa.ForeignKey("stocks.isin", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("cost_estimate", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_ai_runs_isin_agent_created",
        "ai_runs",
        ["isin", "agent_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_runs_isin_agent_created", table_name="ai_runs")
    op.drop_table("ai_runs")

    with op.batch_alter_table("run_stock_status") as batch:
        batch.add_column(
            sa.Column(
                "ai_status",
                sa.String(16),
                nullable=False,
                server_default="not_started",
            )
        )
        batch.add_column(sa.Column("ai_started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("ai_finished_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("ai_error", sa.Text(), nullable=True))

    op.create_table(
        "valuations",
        sa.Column(
            "isin", sa.String(12), sa.ForeignKey("stocks.isin"), primary_key=True
        ),
        sa.Column("fundamental_score", sa.Integer(), nullable=True),
        sa.Column("moat_score", sa.Integer(), nullable=True),
        sa.Column("moat_text", sa.Text(), nullable=True),
        sa.Column("fair_value_dcf", sa.Float(), nullable=True),
        sa.Column("fair_value_nav", sa.Float(), nullable=True),
        sa.Column(
            "recommendation",
            sa.Enum("none", "buy", "risk_buy", name="recommendation"),
            nullable=True,
        ),
        sa.Column("recommendation_reason", sa.Text(), nullable=True),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("field_sources", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("field_locks", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("last_ai_at", sa.DateTime(), nullable=True),
        sa.Column("ai_cost_estimate", sa.Float(), nullable=True),
    )
