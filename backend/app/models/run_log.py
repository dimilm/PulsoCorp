from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stocks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stocks_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stocks_success: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stocks_error: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Lifecycle: queued -> running -> finished. Used by UI to decide whether to poll.
    phase: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunStockStatus(Base):
    __tablename__ = "run_stock_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_logs.id", ondelete="CASCADE"), nullable=False
    )
    isin: Mapped[str] = mapped_column(String(12), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # not_started | running | done | error
    overall_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)

    symbol_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    symbol_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    symbol_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    symbol_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    quote_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    quote_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quote_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    quote_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    metrics_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    metrics_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metrics_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metrics_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    ai_status: Mapped[str] = mapped_column(String(16), default="not_started", nullable=False)
    ai_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_error: Mapped[str | None] = mapped_column(Text, nullable=True)


Index("ix_run_stock_status_run", RunStockStatus.run_id)
Index("ix_run_stock_status_run_isin", RunStockStatus.run_id, RunStockStatus.isin, unique=True)


class JobLock(Base):
    __tablename__ = "job_locks"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Process-id (or generic owner string) of whoever holds the lock. Used to
    # tell whether a stale lock belongs to the current process or a previous
    # crashed one during startup recovery.
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # When the lock was acquired and last touched. The heartbeat is renewed
    # periodically while a refresh runs; a heartbeat older than the configured
    # TTL is treated as a crash and the lock can be reclaimed.
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
