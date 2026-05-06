"""Unit + endpoint tests for the Fisher agent.

The provider is fully mocked – we never call out to OpenAI/Gemini/Ollama.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agents.fisher.agent import FisherAgent
from app.agents.fisher.schema import FISHER_QUESTION_IDS, FisherResult
from app.api.deps import get_ai_provider
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_run import AIRun
from app.models.stock import Stock
from app.providers.ai.base import AIProvider, CompletionResult


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


class _StubProvider(AIProvider):
    name = "stub"
    model = "stub-model"

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def ping(self) -> None:
        return None

    async def complete(self, system_prompt, user_prompt, json_schema=None, temperature=0.2):
        return CompletionResult(
            parsed=self._payload,
            raw_text="{}",
            input_tokens=100,
            output_tokens=50,
            estimated_cost=0.001,
        )


def _sample_fisher_payload() -> dict[str, Any]:
    questions = [
        {"id": qid, "question": qid, "rating": 2, "rationale": "ok"}
        for qid in FISHER_QUESTION_IDS
    ]
    return {
        "questions": questions,
        "total_score": 30,
        "verdict": "strong",
        "summary": "Sehr stark.",
    }


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("FISH%")).delete()
        db.query(Stock).filter(Stock.isin.like("FISH%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("FISH%")).delete()
        db.query(Stock).filter(Stock.isin.like("FISH%")).delete()
        db.commit()
    finally:
        db.close()


def _seed_stock() -> Stock:
    db = SessionLocal()
    try:
        stock = Stock(isin="FISH00000001", name="Fisher Test", sector="Tech", currency="USD")
        db.add(stock)
        db.commit()
        db.refresh(stock)
        return stock
    finally:
        db.close()


def test_fisher_build_input_includes_metrics_and_tags() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        payload = FisherAgent().build_input(db, db.get(Stock, stock.isin))
    finally:
        db.close()
    assert payload["isin"] == "FISH00000001"
    assert payload["name"] == "Fisher Test"
    assert "metrics" in payload
    assert "tags" in payload
    assert isinstance(payload["tags"], list)


def test_fisher_run_persists_done_run_with_parsed_result() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        provider = _StubProvider(_sample_fisher_payload())
        run = asyncio.run(FisherAgent().run(db, provider, db.get(Stock, stock.isin)))
    finally:
        db.close()
    assert run.status == "done"
    assert run.agent_id == "fisher"
    assert run.result_payload is not None
    parsed = FisherResult.model_validate(run.result_payload)
    assert parsed.total_score == 30
    assert parsed.verdict == "strong"
    assert run.cost_estimate == 0.001


def test_fisher_run_records_error_on_invalid_payload() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        provider = _StubProvider({"foo": "bar"})  # missing all required keys
        run = asyncio.run(FisherAgent().run(db, provider, db.get(Stock, stock.isin)))
    finally:
        db.close()
    assert run.status == "error"
    assert run.result_payload is None
    assert run.error_text


def test_fisher_queue_run_creates_running_row_without_provider() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        run = FisherAgent().queue_run(db, db.get(Stock, stock.isin))
        assert run.status == "running"
        assert run.result_payload is None
        assert run.error_text is None
        assert run.duration_ms is None
        assert run.input_payload  # populated via build_input
        assert run.id is not None
    finally:
        db.close()


def test_fisher_execute_run_updates_existing_row_to_done() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        agent = FisherAgent()
        run = agent.queue_run(db, db.get(Stock, stock.isin))
        provider = _StubProvider(_sample_fisher_payload())
        finished = asyncio.run(
            agent.execute_run(db, provider, run, db.get(Stock, stock.isin))
        )
    finally:
        db.close()
    assert finished.id == run.id
    assert finished.status == "done"
    assert finished.provider == "stub"
    assert finished.model == "stub-model"
    assert finished.cost_estimate == 0.001
    assert finished.duration_ms is not None and finished.duration_ms >= 0
    assert finished.result_payload["total_score"] == 30


def test_fisher_endpoint_queues_run_and_resolves_in_background() -> None:
    """The route returns 202 with a running row; the BG task then finishes
    it. With FastAPI's TestClient, background tasks complete before the
    test continues, so we can assert on the persisted row afterwards."""
    from app.api.v1.ai import execute_run_in_background  # noqa: F401

    import app.services.ai_run_service as ai_run_service

    captured_provider = _StubProvider(_sample_fisher_payload())

    def _fake_build(_row):
        return captured_provider

    stock = _seed_stock()
    original_build = ai_run_service.build_ai_provider
    ai_run_service.build_ai_provider = _fake_build  # type: ignore[assignment]
    try:
        client = TestClient(app)
        csrf = _login(client)
        resp = client.post(
            f"/api/v1/ai/agents/fisher/run/{stock.isin}",
            headers={"X-CSRF-Token": csrf},
        )
    finally:
        ai_run_service.build_ai_provider = original_build  # type: ignore[assignment]

    assert resp.status_code == 202
    body = resp.json()
    assert body["agent_id"] == "fisher"
    assert body["status"] == "running"
    assert body["result_payload"] is None
    run_id = body["id"]

    db = SessionLocal()
    try:
        run = db.get(AIRun, run_id)
        assert run is not None
        assert run.status == "done"
        assert run.result_payload["total_score"] == 30
        assert run.cost_estimate == 0.001
    finally:
        db.close()


def test_fisher_endpoint_returns_409_when_run_already_in_flight() -> None:
    stock = _seed_stock()
    db = SessionLocal()
    try:
        existing = FisherAgent().queue_run(db, db.get(Stock, stock.isin))
        assert existing.status == "running"
    finally:
        db.close()

    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        f"/api/v1/ai/agents/fisher/run/{stock.isin}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 409
