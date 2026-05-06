from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.models.base import Base


stock_tags = Table(
    "stock_tags",
    Base.metadata,
    Column("isin", String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_stock_tags_tag_id", "tag_id"),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)


class Stock(Base):
    __tablename__ = "stocks"

    isin: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker_override: Mapped[str | None] = mapped_column(String(24), nullable=True)
    link_yahoo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_finanzen: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_onvista_chart: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_onvista_fundamental: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 1:1 children are eager-loaded so a single Stock fetch returns market /
    # metrics / position data in one round trip. This avoids the N+1 burst we
    # previously hit when the dashboard serialized many rows via to_stock_out.
    market_data = relationship(
        "MarketData",
        uselist=False,
        back_populates="stock",
        cascade="all,delete-orphan",
        lazy="joined",
    )
    metrics = relationship(
        "Metrics",
        uselist=False,
        back_populates="stock",
        cascade="all,delete-orphan",
        lazy="joined",
    )
    position = relationship(
        "Position",
        uselist=False,
        back_populates="stock",
        cascade="all,delete-orphan",
        lazy="joined",
    )
    # Many:many tag list stays selectin so the JOIN tree stays simple.
    tags = relationship("Tag", secondary=stock_tags, lazy="selectin")


Index("ix_stocks_sector", Stock.sector)
Index("ix_stocks_name", Stock.name)


class MarketData(Base):
    __tablename__ = "market_data"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(Enum("ok", "error", name="fetch_status"), default="ok", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock = relationship("Stock", back_populates="market_data")


Index("ix_market_data_last_status", MarketData.last_status)
Index("ix_market_data_last_updated", MarketData.last_updated)


class Metrics(Base):
    __tablename__ = "metrics"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True)
    pe_forward: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_min_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_max_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_avg_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_avg_5y: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyst_target_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    equity_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Float, nullable=True)

    stock = relationship("Stock", back_populates="metrics")


class Position(Base):
    __tablename__ = "positions"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True)
    tranches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stock = relationship("Stock", back_populates="position")


class PriceHistory(Base):
    """Cached OHLC bars per (isin, interval, date).

    The cache is filled on demand by the history endpoint (and TTL-refreshed),
    so we keep it independent of the main refresh pipeline. The interval is
    part of the primary key because we store the same date once per granularity
    (1d / 1wk / 1mo) — the chart picks the appropriate one per range.
    """

    __tablename__ = "price_history"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True)
    interval: Mapped[str] = mapped_column(String(8), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


Index("ix_price_history_isin_interval", PriceHistory.isin, PriceHistory.interval)
