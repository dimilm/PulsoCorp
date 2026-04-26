"""Initial schema baseline.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26

Squashed baseline that creates the full current schema in a single revision.
Replaces the previous chain 0001_initial -> 0002_add_indexes ->
0003_add_price_history -> 0004_ai_agents. The application is not in production
yet, so we collapsed the history instead of carrying four files that together
just describe the live schema.

Local databases that already advanced through the old chain (i.e. carry an
``alembic_version`` row pointing at one of the dropped revisions) are
re-stamped to ``0001_initial`` by ``_run_schema_setup`` in ``app/main.py``,
so no manual SQL or DB reset is required.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(64), primary_key=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "user", name="user_role"),
            nullable=False,
            server_default="user",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("update_hour", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("update_minute", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("update_weekends", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_provider", sa.String(32), nullable=False, server_default="openai"),
        sa.Column("ai_endpoint", sa.String(512), nullable=True),
        sa.Column("ai_api_key_encrypted", sa.String(1024), nullable=True),
        sa.Column("ai_model", sa.String(128), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("ai_refresh_interval", sa.String(16), nullable=False, server_default="monthly"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "stocks",
        sa.Column("isin", sa.String(12), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("sector", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("burggraben", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("ticker_override", sa.String(24), nullable=True),
        sa.Column("link_yahoo", sa.String(512), nullable=True),
        sa.Column("link_finanzen", sa.String(512), nullable=True),
        sa.Column("link_onvista_chart", sa.String(512), nullable=True),
        sa.Column("link_onvista_fundamental", sa.String(512), nullable=True),
    )

    op.create_table(
        "stock_tags",
        sa.Column(
            "isin",
            sa.String(12),
            sa.ForeignKey("stocks.isin", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "market_data",
        sa.Column(
            "isin", sa.String(12), sa.ForeignKey("stocks.isin"), primary_key=True
        ),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("day_change_pct", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column(
            "last_status",
            sa.Enum("ok", "error", name="fetch_status"),
            nullable=False,
            server_default="ok",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "metrics",
        sa.Column(
            "isin", sa.String(12), sa.ForeignKey("stocks.isin"), primary_key=True
        ),
        sa.Column("pe_forward", sa.Float(), nullable=True),
        sa.Column("pe_min_5y", sa.Float(), nullable=True),
        sa.Column("pe_max_5y", sa.Float(), nullable=True),
        sa.Column("pe_avg_5y", sa.Float(), nullable=True),
        sa.Column("dividend_yield_current", sa.Float(), nullable=True),
        sa.Column("dividend_yield_avg_5y", sa.Float(), nullable=True),
        sa.Column("analyst_target_1y", sa.Float(), nullable=True),
        sa.Column("market_cap", sa.Float(), nullable=True),
        sa.Column("equity_ratio", sa.Float(), nullable=True),
        sa.Column("debt_ratio", sa.Float(), nullable=True),
        sa.Column("revenue_growth", sa.Float(), nullable=True),
    )

    op.create_table(
        "positions",
        sa.Column(
            "isin", sa.String(12), sa.ForeignKey("stocks.isin"), primary_key=True
        ),
        sa.Column("tranches", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "run_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stocks_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stocks_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stocks_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stocks_error", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("phase", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
        sa.Column("error_details", sa.Text(), nullable=True),
    )

    op.create_table(
        "run_stock_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("run_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("isin", sa.String(12), nullable=False),
        sa.Column("stock_name", sa.String(255), nullable=True),
        sa.Column("overall_status", sa.String(16), nullable=False, server_default="not_started"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_symbol", sa.String(64), nullable=True),
        sa.Column("symbol_status", sa.String(16), nullable=False, server_default="not_started"),
        sa.Column("symbol_started_at", sa.DateTime(), nullable=True),
        sa.Column("symbol_finished_at", sa.DateTime(), nullable=True),
        sa.Column("symbol_error", sa.Text(), nullable=True),
        sa.Column("quote_status", sa.String(16), nullable=False, server_default="not_started"),
        sa.Column("quote_started_at", sa.DateTime(), nullable=True),
        sa.Column("quote_finished_at", sa.DateTime(), nullable=True),
        sa.Column("quote_error", sa.Text(), nullable=True),
        sa.Column("metrics_status", sa.String(16), nullable=False, server_default="not_started"),
        sa.Column("metrics_started_at", sa.DateTime(), nullable=True),
        sa.Column("metrics_finished_at", sa.DateTime(), nullable=True),
        sa.Column("metrics_error", sa.Text(), nullable=True),
    )

    op.create_table(
        "job_locks",
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("acquired_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
    )

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

    op.create_index("ix_stocks_sector", "stocks", ["sector"])
    op.create_index("ix_stocks_burggraben", "stocks", ["burggraben"])
    op.create_index("ix_stocks_name", "stocks", ["name"])
    op.create_index("ix_stock_tags_tag_id", "stock_tags", ["tag_id"])
    op.create_index("ix_market_data_last_status", "market_data", ["last_status"])
    op.create_index("ix_market_data_last_updated", "market_data", ["last_updated"])
    op.create_index("ix_run_logs_phase", "run_logs", ["phase"])
    op.create_index("ix_run_logs_started_at", "run_logs", ["started_at"])
    op.create_index("ix_run_stock_status_run", "run_stock_status", ["run_id"])
    op.create_index(
        "ix_run_stock_status_run_isin",
        "run_stock_status",
        ["run_id", "isin"],
        unique=True,
    )
    op.create_index(
        "ix_price_history_isin_interval",
        "price_history",
        ["isin", "interval"],
    )
    op.create_index(
        "ix_ai_runs_isin_agent_created",
        "ai_runs",
        ["isin", "agent_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_runs_isin_agent_created", table_name="ai_runs")
    op.drop_index("ix_price_history_isin_interval", table_name="price_history")
    op.drop_index("ix_run_stock_status_run_isin", table_name="run_stock_status")
    op.drop_index("ix_run_stock_status_run", table_name="run_stock_status")
    op.drop_index("ix_run_logs_started_at", table_name="run_logs")
    op.drop_index("ix_run_logs_phase", table_name="run_logs")
    op.drop_index("ix_market_data_last_updated", table_name="market_data")
    op.drop_index("ix_market_data_last_status", table_name="market_data")
    op.drop_index("ix_stock_tags_tag_id", table_name="stock_tags")
    op.drop_index("ix_stocks_name", table_name="stocks")
    op.drop_index("ix_stocks_burggraben", table_name="stocks")
    op.drop_index("ix_stocks_sector", table_name="stocks")

    op.drop_table("ai_runs")
    op.drop_table("price_history")
    op.drop_table("job_locks")
    op.drop_table("run_stock_status")
    op.drop_table("run_logs")
    op.drop_table("positions")
    op.drop_table("metrics")
    op.drop_table("market_data")
    op.drop_table("stock_tags")
    op.drop_table("stocks")
    op.drop_table("tags")
    op.drop_table("app_settings")
    op.drop_table("users")

    sa.Enum(name="fetch_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
