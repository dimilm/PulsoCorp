"""AI service tests focused on the fallback handling.

The provider is a tiny stub so we can exercise the persistence logic without
going through OpenAI/Ollama.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.db.session import SessionLocal
from app.models.stock import Stock, Valuation
from app.providers.ai.base import AIEvaluation, AIProvider
from app.services.ai_service import (
    SOURCE_AI,
    SOURCE_AI_FALLBACK,
    AIService,
)


class _StubProvider(AIProvider):
    def __init__(self, evaluation: AIEvaluation) -> None:
        self._evaluation = evaluation
        self.calls = 0

    async def evaluate(self, payload: dict[str, Any]) -> AIEvaluation:  # type: ignore[override]
        self.calls += 1
        return self._evaluation


def _make_eval(*, is_fallback: bool, recommendation: str = "buy") -> AIEvaluation:
    return AIEvaluation(
        fundamental_score=8,
        moat_score=7,
        moat_text="Stub moat",
        fair_value_dcf=120.0,
        fair_value_nav=110.0,
        recommendation=recommendation,
        recommendation_reason="Because reasons",
        risk_notes="Watch FX",
        estimated_cost=0.0,
        is_fallback=is_fallback,
    )


@pytest.fixture()
def stock_isin() -> str:
    """Insert a clean stock + clean valuation for each test."""
    isin = "US000AISERV1"
    db = SessionLocal()
    try:
        existing = db.get(Stock, isin)
        if existing is None:
            db.add(
                Stock(
                    isin=isin,
                    name="AI Service Stock",
                    sector="Tech",
                    currency="USD",
                    burggraben=False,
                    tranches=0,
                )
            )
        db.query(Valuation).filter(Valuation.isin == isin).delete()
        db.commit()
    finally:
        db.close()
    return isin


def test_real_evaluation_writes_ki_source(stock_isin: str) -> None:
    provider = _StubProvider(_make_eval(is_fallback=False, recommendation="buy"))
    service = AIService(provider)

    db = SessionLocal()
    try:
        stock = db.get(Stock, stock_isin)
        valuation = asyncio.run(service.evaluate_stock(db, stock, force=True))
        db.commit()

        assert provider.calls == 1
        assert valuation.recommendation == "buy"
        assert valuation.field_sources["recommendation"] == SOURCE_AI
        assert valuation.field_sources["fundamental_score"] == SOURCE_AI
        assert valuation.fundamental_score == 8
    finally:
        db.close()


def test_fallback_does_not_apply_buy_recommendation(stock_isin: str) -> None:
    provider = _StubProvider(_make_eval(is_fallback=True, recommendation="buy"))
    service = AIService(provider)

    db = SessionLocal()
    try:
        stock = db.get(Stock, stock_isin)
        valuation = asyncio.run(service.evaluate_stock(db, stock, force=True))
        db.commit()

        # Heuristic recommendation must not be auto-applied.
        assert valuation.recommendation == "none"
        assert valuation.field_sources["recommendation"] == SOURCE_AI_FALLBACK
        assert "Heuristischer Vorschlag" in (valuation.recommendation_reason or "")
        # The numeric fields are still updated, just marked as fallback.
        assert valuation.fundamental_score == 8
        assert valuation.field_sources["fundamental_score"] == SOURCE_AI_FALLBACK
    finally:
        db.close()


def test_fallback_keeps_existing_user_recommendation(stock_isin: str) -> None:
    """A previous recommendation must survive a heuristic refresh."""
    db = SessionLocal()
    try:
        db.add(
            Valuation(
                isin=stock_isin,
                recommendation="hold",
                recommendation_reason="set by user",
            )
        )
        db.commit()
    finally:
        db.close()

    provider = _StubProvider(_make_eval(is_fallback=True, recommendation="risk_buy"))
    service = AIService(provider)

    db = SessionLocal()
    try:
        stock = db.get(Stock, stock_isin)
        valuation = asyncio.run(service.evaluate_stock(db, stock, force=True))
        db.commit()
        assert valuation.recommendation == "hold"
        assert valuation.field_sources["recommendation"] == SOURCE_AI_FALLBACK
    finally:
        db.close()


def test_recent_run_is_skipped_without_force(stock_isin: str) -> None:
    """A second call within `refresh_days` must not re-invoke the provider."""
    provider = _StubProvider(_make_eval(is_fallback=False))
    service = AIService(provider)

    db = SessionLocal()
    try:
        stock = db.get(Stock, stock_isin)
        asyncio.run(service.evaluate_stock(db, stock, force=True))
        db.commit()

        before = provider.calls
        asyncio.run(service.evaluate_stock(db, stock, refresh_days=30, force=False))
        assert provider.calls == before
    finally:
        db.close()
