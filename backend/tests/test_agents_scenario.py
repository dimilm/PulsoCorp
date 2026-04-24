"""Tests for the bull/base/bear scenario agent."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.scenario.agent import ScenarioAgent
from app.agents.scenario.schema import ScenarioResult
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
        "bull": {"assumptions": ["Markt wächst stark"], "target_price": 200.0, "probability": 0.3},
        "base": {"assumptions": ["Markt stabil"], "target_price": 150.0, "probability": 0.5},
        "bear": {"assumptions": ["Rezession"], "target_price": 80.0, "probability": 0.2},
        "expected_value": 151.0,
        "expected_return_pct": 12.0,
        "time_horizon_years": 3,
        "summary": "Solides Risiko/Rendite-Profil.",
    }


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("SCEN%")).delete()
        db.query(Stock).filter(Stock.isin.like("SCEN%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("SCEN%")).delete()
        db.query(Stock).filter(Stock.isin.like("SCEN%")).delete()
        db.commit()
    finally:
        db.close()


def test_scenario_run_validates_probability_and_persists() -> None:
    db = SessionLocal()
    try:
        stock = Stock(isin="SCEN00000001", name="Scenario Test")
        db.add(stock)
        db.commit()
        run = asyncio.run(
            ScenarioAgent().run(db, _StubProvider(_payload()), db.get(Stock, stock.isin))
        )
    finally:
        db.close()
    assert run.status == "done"
    parsed = ScenarioResult.model_validate(run.result_payload)
    assert parsed.expected_return_pct == 12.0


def test_scenario_run_rejects_payload_with_bad_probabilities() -> None:
    bad = _payload()
    bad["bull"]["probability"] = 0.9
    db = SessionLocal()
    try:
        stock = Stock(isin="SCEN00000002", name="Bad Probs")
        db.add(stock)
        db.commit()
        run = asyncio.run(
            ScenarioAgent().run(db, _StubProvider(bad), db.get(Stock, stock.isin))
        )
    finally:
        db.close()
    assert run.status == "error"
    assert run.error_text
