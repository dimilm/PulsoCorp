"""Persisted history of AI agent runs.

Each row captures a single invocation of one agent against one stock: which
provider/model was used, the input payload that was sent to the LLM, the
parsed result (or error message on failure), token-cost estimate and total
duration. The table is the sole source of truth for the per-stock AI history
panel in the UI.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.models.base import Base


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isin: Mapped[str] = mapped_column(
        String(12), ForeignKey("stocks.isin", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # "done" | "error"
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


Index(
    "ix_ai_runs_isin_agent_created",
    AIRun.isin,
    AIRun.agent_id,
    AIRun.created_at.desc(),
)
