"""Tests for the red-flag agent."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.redflag.agent import RedFlagAgent
from app.agents.redflag.schema import RedFlagResult
from app.db.session import SessionLocal
from app.models.ai_run import AIRun
from app.models.stock import Stock
from app.providers.ai.base import AIProvider, CompletionResult


class _StubProvider(AIProvider):
    name = "stub"
    model = "stub-model"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def ping(self) -> None:
        return None

    async def complete(self, system_prompt, user_prompt, json_schema=None, temperature=0.2):
        return CompletionResult(parsed=self._payload, raw_text="{}")


def _payload() -> dict[str, Any]:
    return {
        "flags": [
            {
                "category": "leverage",
                "severity": "high",
                "title": "Hohe Verschuldung",
                "description": "Debt-Ratio > 0.7",
                "evidence_hint": "metrics.debt_ratio",
            },
            {
                "category": "concentration",
                "severity": "med",
                "title": "Großkundenrisiko",
                "description": "Top-3 Kunden machen 60% des Umsatzes aus",
                "evidence_hint": "Geschäftsbericht S.42",
            },
        ],
        "overall_risk": "high",
        "summary": "Verschuldung dominiert das Risikoprofil.",
    }


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("REDF%")).delete()
        db.query(Stock).filter(Stock.isin.like("REDF%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("REDF%")).delete()
        db.query(Stock).filter(Stock.isin.like("REDF%")).delete()
        db.commit()
    finally:
        db.close()


def test_redflag_run_persists_flags() -> None:
    db = SessionLocal()
    try:
        stock = Stock(isin="REDF00000001", name="RedFlag Test")
        db.add(stock)
        db.commit()
        run = asyncio.run(
            RedFlagAgent().run(db, _StubProvider(_payload()), db.get(Stock, stock.isin))
        )
    finally:
        db.close()
    assert run.status == "done"
    parsed = RedFlagResult.model_validate(run.result_payload)
    assert parsed.overall_risk == "high"
    assert len(parsed.flags) == 2
    assert parsed.flags[0].category == "leverage"


def test_redflag_run_handles_empty_flag_list() -> None:
    db = SessionLocal()
    try:
        stock = Stock(isin="REDF00000002", name="Clean Stock")
        db.add(stock)
        db.commit()
        empty = {"flags": [], "overall_risk": "low", "summary": "Keine Auffälligkeiten."}
        run = asyncio.run(
            RedFlagAgent().run(db, _StubProvider(empty), db.get(Stock, stock.isin))
        )
    finally:
        db.close()
    assert run.status == "done"
    parsed = RedFlagResult.model_validate(run.result_payload)
    assert parsed.flags == []
    assert parsed.overall_risk == "low"
