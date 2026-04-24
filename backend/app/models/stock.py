from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


stock_tags = Table(
    "stock_tags",
    Base.metadata,
    Column("isin", String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
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
    burggraben: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker_override: Mapped[str | None] = mapped_column(String(24), nullable=True)
    link_yahoo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_finanzen: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_onvista_chart: Mapped[str | None] = mapped_column(String(512), nullable=True)
    link_onvista_fundamental: Mapped[str | None] = mapped_column(String(512), nullable=True)

    market_data = relationship("MarketData", uselist=False, back_populates="stock", cascade="all,delete-orphan")
    metrics = relationship("Metrics", uselist=False, back_populates="stock", cascade="all,delete-orphan")
    valuation = relationship("Valuation", uselist=False, back_populates="stock", cascade="all,delete-orphan")
    position = relationship("Position", uselist=False, back_populates="stock", cascade="all,delete-orphan")
    tags = relationship("Tag", secondary=stock_tags, lazy="selectin")


class MarketData(Base):
    __tablename__ = "market_data"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin"), primary_key=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(Enum("ok", "error", name="fetch_status"), default="ok", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    stock = relationship("Stock", back_populates="market_data")


class Metrics(Base):
    __tablename__ = "metrics"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin"), primary_key=True)
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


class Valuation(Base):
    __tablename__ = "valuations"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin"), primary_key=True)
    fundamental_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moat_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moat_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fair_value_dcf: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_value_nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(
        Enum("none", "buy", "risk_buy", name="recommendation"), nullable=True
    )
    recommendation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_sources: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    field_locks: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    last_ai_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    stock = relationship("Stock", back_populates="valuation")


class Position(Base):
    __tablename__ = "positions"

    isin: Mapped[str] = mapped_column(String(12), ForeignKey("stocks.isin"), primary_key=True)
    tranches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stock = relationship("Stock", back_populates="position")
