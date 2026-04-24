"""Tests for the AI agents router (`/api/v1/ai/...`)."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_run import AIRun
from app.models.stock import Stock


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("ROUT%")).delete()
        db.query(Stock).filter(Stock.isin.like("ROUT%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("ROUT%")).delete()
        db.query(Stock).filter(Stock.isin.like("ROUT%")).delete()
        db.commit()
    finally:
        db.close()


def test_get_agents_returns_all_registered_agents() -> None:
    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/ai/agents")
    assert resp.status_code == 200
    body = resp.json()
    ids = {agent["id"] for agent in body}
    assert ids == {"fisher", "tournament", "scenario", "redflag"}
    fisher = next(a for a in body if a["id"] == "fisher")
    assert "output_schema" in fisher
    assert fisher["output_schema"]["type"] == "object"


def test_get_agent_prompt_returns_plain_text() -> None:
    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/ai/agents/fisher/prompt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "Fisher" in resp.text


def test_get_agent_prompt_returns_404_for_unknown_agent() -> None:
    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/ai/agents/does-not-exist/prompt")
    assert resp.status_code == 404


def test_list_agent_runs_returns_history_in_desc_order() -> None:
    db = SessionLocal()
    try:
        db.add(Stock(isin="ROUT00000001", name="Router Test"))
        db.flush()
        for idx in range(3):
            db.add(
                AIRun(
                    isin="ROUT00000001",
                    agent_id="fisher",
                    created_at=datetime(2026, 4, idx + 1, 12, 0, 0),
                    provider="stub",
                    model="stub",
                    status="done",
                    input_payload={"i": idx},
                    result_payload={"total_score": idx},
                )
            )
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    _login(client)
    resp = client.get("/api/v1/ai/agents/fisher/runs/ROUT00000001")
    assert resp.status_code == 200
    body = resp.json()
    assert [r["result_payload"]["total_score"] for r in body] == [2, 1, 0]


def test_get_run_returns_full_payload() -> None:
    db = SessionLocal()
    try:
        db.add(Stock(isin="ROUT00000002", name="Router Detail"))
        run = AIRun(
            isin="ROUT00000002",
            agent_id="redflag",
            created_at=utcnow(),
            provider="stub",
            model="stub",
            status="done",
            input_payload={"k": "v"},
            result_payload={"flags": []},
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    client = TestClient(app)
    _login(client)
    resp = client.get(f"/api/v1/ai/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == "redflag"
    assert body["input_payload"] == {"k": "v"}
    assert body["result_payload"] == {"flags": []}


def test_run_agent_requires_csrf() -> None:
    db = SessionLocal()
    try:
        db.add(Stock(isin="ROUT00000003", name="CSRF Test"))
        db.commit()
    finally:
        db.close()
    client = TestClient(app)
    _login(client)
    resp = client.post("/api/v1/ai/agents/fisher/run/ROUT00000003")
    assert resp.status_code == 403


def test_run_agent_returns_404_for_unknown_isin() -> None:
    client = TestClient(app)
    csrf = _login(client)
    resp = client.post(
        "/api/v1/ai/agents/fisher/run/ROUT99999999",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 404
