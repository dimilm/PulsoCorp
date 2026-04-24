"""Tests for the peer-tournament agent."""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.agents.tournament.agent import TournamentAgent
from app.agents.tournament.schema import TOURNAMENT_CATEGORIES, TournamentResult
from app.db.session import SessionLocal
from app.models.ai_run import AIRun
from app.models.stock import Stock
from app.providers.ai.base import AIProvider, CompletionResult


class _SequentialProvider(AIProvider):
    """Returns successive payloads for each `complete()` call.

    The tournament invokes the provider once per match; we let the test
    enumerate the expected match outcomes in deterministic order.
    """

    name = "stub"
    model = "stub-model"

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = list(payloads)

    async def ping(self) -> None:
        return None

    async def complete(self, system_prompt, user_prompt, json_schema=None, temperature=0.2):
        if not self._payloads:
            raise RuntimeError("Mehr Match-Aufrufe als erwartet")
        payload = self._payloads.pop(0)
        return CompletionResult(parsed=payload, raw_text="{}", estimated_cost=0.0005)


def _match(winner: str = "a") -> dict[str, Any]:
    return {
        "category_scores": {cat: {"a": 2, "b": 2} for cat in TOURNAMENT_CATEGORIES},
        "winner": winner,
        "rationale": "stub",
    }


@pytest.fixture(autouse=True)
def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("TOUR%")).delete()
        db.query(Stock).filter(Stock.isin.like("TOUR%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(AIRun).filter(AIRun.isin.like("TOUR%")).delete()
        db.query(Stock).filter(Stock.isin.like("TOUR%")).delete()
        db.commit()
    finally:
        db.close()


def _seed_with_peers(count: int) -> Stock:
    db = SessionLocal()
    try:
        main = Stock(isin="TOUR00000001", name="Main", sector="Tech", currency="USD")
        db.add(main)
        for i in range(count):
            isin = f"TOUR0000010{i}"
            db.add(Stock(isin=isin, name=f"Peer {i}", sector="Tech", currency="USD"))
        db.commit()
        db.refresh(main)
        return main
    finally:
        db.close()


def test_tournament_build_input_uses_explicit_peers() -> None:
    main = _seed_with_peers(3)
    db = SessionLocal()
    try:
        payload = TournamentAgent().build_input(
            db, db.get(Stock, main.isin), peers=["TOUR00000100", "TOUR00000101"]
        )
    finally:
        db.close()
    isins = [p["isin"] for p in payload["participants"]]
    assert isins[0] == "TOUR00000001"
    assert "TOUR00000100" in isins
    assert "TOUR00000101" in isins


def test_tournament_run_advances_winner_to_final() -> None:
    main = _seed_with_peers(1)
    db = SessionLocal()
    try:
        provider = _SequentialProvider([_match(winner="a")])  # 2 participants → 1 match
        run = asyncio.run(
            TournamentAgent().run(db, provider, db.get(Stock, main.isin), peers=["TOUR00000100"])
        )
    finally:
        db.close()
    assert run.status == "done"
    parsed = TournamentResult.model_validate(run.result_payload)
    assert parsed.winner_isin == "TOUR00000001"
    assert len(parsed.rounds) == 1
    assert parsed.rounds[0][0].winner == "TOUR00000001"


def test_tournament_run_records_error_when_only_main_stock_present() -> None:
    main = _seed_with_peers(0)
    db = SessionLocal()
    try:
        provider = _SequentialProvider([])
        run = asyncio.run(
            TournamentAgent().run(db, provider, db.get(Stock, main.isin), peers=[])
        )
    finally:
        db.close()
    assert run.status == "error"
    assert run.error_text and "Teilnehmer" in run.error_text
