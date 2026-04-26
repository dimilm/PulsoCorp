"""Tests for the latest-AI-run lookup that powers the watchlist pills."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.ai_run import AIRun
from app.models.stock import Stock
from app.services.ai_run_lookup import (
    build_latest_run_summaries,
    latest_done_runs_by_isin,
    summarize_run,
)


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("AILK%")).delete()
        db.query(Stock).filter(Stock.isin.like("AILK%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("AILK%")).delete()
        db.query(Stock).filter(Stock.isin.like("AILK%")).delete()
        db.commit()
    finally:
        db.close()


def _seed_stock(db, isin: str, name: str = "Test") -> None:
    db.merge(Stock(isin=isin, name=name, sector="Tech"))
    db.flush()


def _add_run(
    db,
    *,
    isin: str,
    agent_id: str,
    created_at: datetime,
    status: str = "done",
    input_payload: dict | None = None,
    result_payload: dict | None = None,
) -> AIRun:
    run = AIRun(
        isin=isin,
        agent_id=agent_id,
        created_at=created_at,
        provider="stub",
        model="gpt-stub",
        status=status,
        input_payload=input_payload or {},
        result_payload=result_payload,
    )
    db.add(run)
    db.flush()
    return run


def test_latest_done_runs_picks_most_recent_per_agent() -> None:
    db = SessionLocal()
    try:
        _seed_stock(db, "AILK00000001")
        _add_run(
            db,
            isin="AILK00000001",
            agent_id="fisher",
            created_at=datetime(2026, 4, 1, 12, 0, 0),
            result_payload={"total_score": 10, "verdict": "weak", "questions": []},
        )
        newest = _add_run(
            db,
            isin="AILK00000001",
            agent_id="fisher",
            created_at=datetime(2026, 4, 10, 12, 0, 0),
            result_payload={"total_score": 24, "verdict": "strong", "questions": []},
        )
        _add_run(
            db,
            isin="AILK00000001",
            agent_id="redflag",
            created_at=datetime(2026, 4, 5, 12, 0, 0),
            result_payload={"flags": [{"x": 1}], "overall_risk": "low", "summary": ""},
        )
        db.commit()

        result = latest_done_runs_by_isin(db, ["AILK00000001"])
        assert set(result["AILK00000001"].keys()) == {"fisher", "redflag"}
        assert result["AILK00000001"]["fisher"].id == newest.id
    finally:
        db.close()


def test_latest_done_runs_excludes_error_and_running() -> None:
    db = SessionLocal()
    try:
        _seed_stock(db, "AILK00000002")
        ok = _add_run(
            db,
            isin="AILK00000002",
            agent_id="fisher",
            created_at=datetime(2026, 4, 1, 12, 0, 0),
            result_payload={"total_score": 12, "verdict": "neutral", "questions": []},
        )
        # Newer but failed — must be ignored, the older "done" wins.
        _add_run(
            db,
            isin="AILK00000002",
            agent_id="fisher",
            created_at=datetime(2026, 4, 11, 12, 0, 0),
            status="error",
        )
        _add_run(
            db,
            isin="AILK00000002",
            agent_id="fisher",
            created_at=datetime(2026, 4, 12, 12, 0, 0),
            status="running",
        )
        db.commit()

        result = latest_done_runs_by_isin(db, ["AILK00000002"])
        assert result["AILK00000002"]["fisher"].id == ok.id
    finally:
        db.close()


def test_summarize_run_fisher() -> None:
    run = AIRun(
        isin="AILK00000003",
        agent_id="fisher",
        created_at=datetime(2026, 4, 1),
        provider="stub",
        model="m",
        status="done",
        input_payload={},
        result_payload={"total_score": 22, "verdict": "strong", "questions": []},
    )
    assert summarize_run(run) == {"score": 22, "verdict": "strong"}


def test_summarize_run_redflag_counts_flags() -> None:
    run = AIRun(
        isin="AILK00000004",
        agent_id="redflag",
        created_at=datetime(2026, 4, 1),
        provider="stub",
        model="m",
        status="done",
        input_payload={},
        result_payload={
            "overall_risk": "med",
            "flags": [{"a": 1}, {"b": 2}, {"c": 3}],
            "summary": "",
        },
    )
    assert summarize_run(run) == {"overall_risk": "med", "flag_count": 3}


def test_summarize_run_scenario() -> None:
    run = AIRun(
        isin="AILK00000005",
        agent_id="scenario",
        created_at=datetime(2026, 4, 1),
        provider="stub",
        model="m",
        status="done",
        input_payload={},
        result_payload={"expected_return_pct": 12.5},
    )
    assert summarize_run(run) == {"expected_return_pct": 12.5}


def test_summarize_run_tournament_only_when_main_isin_matches() -> None:
    own_bracket = AIRun(
        isin="AILK00000006",
        agent_id="tournament",
        created_at=datetime(2026, 4, 1),
        provider="stub",
        model="m",
        status="done",
        input_payload={
            "main_isin": "AILK00000006",
            "participants": [
                {"isin": "AILK00000006"},
                {"isin": "PEER00000001"},
                {"isin": "PEER00000002"},
            ],
        },
        result_payload={"winner_isin": "AILK00000006"},
    )
    summary = summarize_run(own_bracket)
    assert summary == {
        "is_winner": True,
        "winner_isin": "AILK00000006",
        "peer_count": 2,
    }

    foreign_bracket = AIRun(
        isin="AILK00000006",
        agent_id="tournament",
        created_at=datetime(2026, 4, 2),
        provider="stub",
        model="m",
        status="done",
        # `main_isin` differs → this stock was a peer, not the protagonist.
        input_payload={
            "main_isin": "PEER00000001",
            "participants": [{"isin": "PEER00000001"}, {"isin": "AILK00000006"}],
        },
        result_payload={"winner_isin": "PEER00000001"},
    )
    assert summarize_run(foreign_bracket) is None


def test_build_latest_run_summaries_filters_tournament_peer_runs() -> None:
    db = SessionLocal()
    try:
        _seed_stock(db, "AILK00000007", name="Main")
        # Tournament run where the stock was just a peer — must NOT show up
        # in the per-stock summary even though it is the latest tournament
        # run referencing this ISIN.
        _add_run(
            db,
            isin="AILK00000007",
            agent_id="tournament",
            created_at=datetime(2026, 4, 1),
            input_payload={
                "main_isin": "OTHER0000001",
                "participants": [
                    {"isin": "OTHER0000001"},
                    {"isin": "AILK00000007"},
                ],
            },
            result_payload={"winner_isin": "OTHER0000001"},
        )
        # Older Fisher run that should still surface.
        _add_run(
            db,
            isin="AILK00000007",
            agent_id="fisher",
            created_at=datetime(2026, 3, 1),
            result_payload={"total_score": 18, "verdict": "neutral", "questions": []},
        )
        db.commit()

        summaries = build_latest_run_summaries(db, ["AILK00000007"])
        per_agent = summaries.get("AILK00000007", {})
        assert "tournament" not in per_agent
        assert per_agent["fisher"]["summary"] == {"score": 18, "verdict": "neutral"}
    finally:
        db.close()


def test_get_stocks_endpoint_includes_latest_ai_runs() -> None:
    db = SessionLocal()
    try:
        _seed_stock(db, "AILK00000008", name="Endpoint Test")
        _add_run(
            db,
            isin="AILK00000008",
            agent_id="fisher",
            created_at=datetime(2026, 4, 5, 9, 0, 0),
            result_payload={"total_score": 26, "verdict": "strong", "questions": []},
        )
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert resp.status_code == 200

    resp = client.get("/api/v1/stocks", params={"query": "AILK00000008"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    runs = rows[0]["latest_ai_runs"]
    assert "fisher" in runs
    assert runs["fisher"]["summary"] == {"score": 26, "verdict": "strong"}
    assert runs["fisher"]["model"] == "gpt-stub"


def test_get_stock_detail_endpoint_includes_latest_ai_runs() -> None:
    db = SessionLocal()
    try:
        _seed_stock(db, "AILK00000009", name="Detail Test")
        _add_run(
            db,
            isin="AILK00000009",
            agent_id="redflag",
            created_at=datetime(2026, 4, 6, 9, 0, 0),
            result_payload={
                "overall_risk": "high",
                "flags": [{"x": 1}, {"y": 2}],
                "summary": "",
            },
        )
        db.commit()
    finally:
        db.close()

    client = TestClient(app)
    resp = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "changeme"}
    )
    assert resp.status_code == 200

    resp = client.get("/api/v1/stocks/AILK00000009")
    assert resp.status_code == 200
    body = resp.json()
    assert body["latest_ai_runs"]["redflag"]["summary"] == {
        "overall_risk": "high",
        "flag_count": 2,
    }
