"""Add job-tracking tables and run-type column.

Revision ID: 0002_job_sources
Revises: 0001_initial
Create Date: 2026-05-03

Introduces the career-portal scrape feature ported from the standalone
`11_JobCounter` project:

* `job_sources`        – per-portal config (URL + adapter type + JSON settings).
* `job_snapshots`      – daily count history, UNIQUE per (source, date).
* `run_job_status`     – per-source row for a `run_type='jobs'` RunLog.
* `run_logs.run_type`  – discriminator column ('market' | 'jobs').
* `app_settings.jobs_*` – cron + enable toggle for the daily scrape.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_job_sources"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "run_logs",
        sa.Column(
            "run_type",
            sa.String(16),
            nullable=False,
            server_default="market",
        ),
    )
    op.create_index("ix_run_logs_run_type", "run_logs", ["run_type"])

    op.add_column(
        "app_settings",
        sa.Column(
            "jobs_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "jobs_update_hour",
            sa.Integer(),
            nullable=False,
            server_default="2",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column(
            "jobs_update_minute",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "isin",
            sa.String(12),
            sa.ForeignKey("stocks.isin", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("portal_url", sa.String(512), nullable=False),
        sa.Column("adapter_type", sa.String(64), nullable=False),
        sa.Column("adapter_settings", sa.JSON(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_job_sources_isin", "job_sources", ["isin"])
    op.create_index("ix_job_sources_is_active", "job_sources", ["is_active"])

    op.create_table(
        "job_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_source_id",
            sa.Integer(),
            sa.ForeignKey("job_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("jobs_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("run_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_meta", sa.JSON(), nullable=False),
    )
    op.create_index(
        "uq_job_snapshots_source_date",
        "job_snapshots",
        ["job_source_id", "snapshot_date"],
        unique=True,
    )
    op.create_index("ix_job_snapshots_date", "job_snapshots", ["snapshot_date"])
    op.create_index("ix_job_snapshots_run", "job_snapshots", ["run_id"])

    op.create_table(
        "run_job_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("run_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_source_id",
            sa.Integer(),
            sa.ForeignKey("job_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column(
            "overall_status",
            sa.String(16),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("jobs_count", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_run_job_status_run", "run_job_status", ["run_id"])
    op.create_index(
        "ix_run_job_status_run_source",
        "run_job_status",
        ["run_id", "job_source_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_run_job_status_run_source", table_name="run_job_status")
    op.drop_index("ix_run_job_status_run", table_name="run_job_status")
    op.drop_table("run_job_status")

    op.drop_index("ix_job_snapshots_run", table_name="job_snapshots")
    op.drop_index("ix_job_snapshots_date", table_name="job_snapshots")
    op.drop_index("uq_job_snapshots_source_date", table_name="job_snapshots")
    op.drop_table("job_snapshots")

    op.drop_index("ix_job_sources_is_active", table_name="job_sources")
    op.drop_index("ix_job_sources_isin", table_name="job_sources")
    op.drop_table("job_sources")

    op.drop_column("app_settings", "jobs_update_minute")
    op.drop_column("app_settings", "jobs_update_hour")
    op.drop_column("app_settings", "jobs_enabled")

    op.drop_index("ix_run_logs_run_type", table_name="run_logs")
    op.drop_column("run_logs", "run_type")
