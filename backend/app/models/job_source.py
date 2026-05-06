"""Career-portal scrape sources and their daily job-count snapshots.

A `JobSource` describes one scrapeable career portal (URL + adapter type +
adapter-specific settings). It can be linked to a `Stock` via ISIN so the
detail page shows the open-position trend next to the price chart, but the
foreign key is `nullable` so admins can also track companies that do not
exist in the watchlist (e.g. private firms). One stock may have multiple
sources (`Volkswagen Group` runs several portals), hence 1:N.

`JobSnapshot` stores the result of one successful scrape; one row per source
per day (UNIQUE(job_source_id, snapshot_date)) so re-running the cron on the
same day idempotently overwrites instead of duplicating.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.models.base import Base


class JobSource(Base):
    __tablename__ = "job_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Optional link to a watchlist stock. SET NULL on stock delete so manually
    # configured sources outlive a temporary stock removal.
    isin: Mapped[str | None] = mapped_column(
        String(12), ForeignKey("stocks.isin", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    portal_url: Mapped[str] = mapped_column(String(512), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Free-form JSON because the schema differs per adapter (selectors,
    # endpoint, payload, headers, ...). Validated by the adapter at runtime.
    adapter_settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    snapshots = relationship(
        "JobSnapshot",
        back_populates="source",
        cascade="all,delete-orphan",
        lazy="selectin",
    )


Index("ix_job_sources_isin", JobSource.isin)
Index("ix_job_sources_is_active", JobSource.is_active)


class JobSnapshot(Base):
    __tablename__ = "job_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    jobs_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # Optional link to the run that produced this snapshot; `NULL` means the
    # row was created via manual import (e.g. CSV/JSON history migration).
    run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("run_logs.id", ondelete="SET NULL"), nullable=True
    )
    raw_meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    source = relationship("JobSource", back_populates="snapshots")


# UNIQUE makes the daily UPSERT trivial via merge() and lets us look up the
# latest count per source with a simple ORDER BY snapshot_date DESC LIMIT 1.
UniqueConstraint(
    JobSnapshot.job_source_id,
    JobSnapshot.snapshot_date,
    name="uq_job_snapshots_source_date",
)
Index(
    "uq_job_snapshots_source_date",
    JobSnapshot.job_source_id,
    JobSnapshot.snapshot_date,
    unique=True,
)
Index("ix_job_snapshots_date", JobSnapshot.snapshot_date)
Index("ix_job_snapshots_run", JobSnapshot.run_id)


class RunJobStatus(Base):
    """Per-source status row for a `run_type='jobs'` RunLog.

    Mirrors `RunStockStatus` but for the simpler jobs pipeline (one network
    call per source -> one outcome). Stored separately from `run_stock_status`
    so a market-data run leaves it untouched and vice versa.
    """

    __tablename__ = "run_job_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_logs.id", ondelete="CASCADE"), nullable=False
    )
    job_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_sources.id", ondelete="CASCADE"), nullable=False
    )
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)

    # not_started | running | done | error | cancelled
    overall_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jobs_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


Index("ix_run_job_status_run", RunJobStatus.run_id)
Index(
    "ix_run_job_status_run_source",
    RunJobStatus.run_id,
    RunJobStatus.job_source_id,
    unique=True,
)
