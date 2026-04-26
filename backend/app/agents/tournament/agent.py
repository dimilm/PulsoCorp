"""Peer-Tournament agent.

The agent assembles a single-elimination bracket from the main stock plus
N peer ISINs (default: same-sector watchlist suggestions). Each match is a
separate LLM call because the model only has to compare two profiles at a
time, which keeps prompts small and the per-call cost predictable.

Bracket sizes are powers of two; we pad with byes when fewer than 8 peers
are available so the structure stays uniform for the UI.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.agents.tournament.schema import (
    TOURNAMENT_CATEGORIES,
    CompanyProfile,
    Match,
    MatchScore,
    SingleMatch,
    TournamentResult,
)
from app.models.ai_run import AIRun
from app.models.stock import MarketData, Metrics, Stock
from app.providers.ai.base import AIProvider, CompletionResult
from app.services.stock_service import find_similar_stocks

MAX_BRACKET_SIZE = 8


class TournamentAgent(BaseAgent):
    id = "tournament"
    name = "Peer-Tournament"
    description = (
        "Lässt das Unternehmen im Bracket-System gegen Peers aus dem gleichen "
        "Sektor antreten. Jedes Match wird in 7 Kategorien bewertet "
        "(Burggraben, Wachstum, Profitabilität, Bilanz, Bewertung, Management, "
        "Risiko)."
    )
    prompt_path = Path(__file__).with_name("prompt.md")
    output_schema = TournamentResult

    def build_input(
        self, db: Session, stock: Stock, *, peers: list[str] | None = None, **_: Any
    ) -> dict[str, Any]:
        """Resolve the bracket participants without performing any LLM calls.

        We persist this payload as the agent input so the user can later see
        which peers were considered, even if the bracket itself is built in
        many separate LLM calls inside `run()`.
        """
        peer_isins = self._resolve_peers(db, stock, peers)
        bracket = [self._profile_for(db, stock).model_dump()]
        for isin in peer_isins:
            peer = db.get(Stock, isin)
            if peer is not None:
                bracket.append(self._profile_for(db, peer).model_dump())
        return {"main_isin": stock.isin, "participants": bracket}

    def _resolve_peers(
        self, db: Session, stock: Stock, peers: list[str] | None
    ) -> list[str]:
        if peers:
            cleaned = [p.strip().upper() for p in peers if p and p.strip()]
            return [p for p in cleaned if p != stock.isin][: MAX_BRACKET_SIZE - 1]
        suggestions = find_similar_stocks(db, stock, limit=MAX_BRACKET_SIZE - 1)
        return [s["isin"] for s in suggestions if s["isin"] != stock.isin]

    def _profile_for(self, db: Session, stock: Stock) -> CompanyProfile:
        market = db.get(MarketData, stock.isin)
        m = db.get(Metrics, stock.isin)
        return CompanyProfile(
            isin=stock.isin,
            name=stock.name,
            sector=stock.sector,
            metrics={
                "current_price": market.current_price if market else None,
                "pe_forward": m.pe_forward if m else None,
                "revenue_growth": m.revenue_growth if m else None,
                "equity_ratio": m.equity_ratio if m else None,
                "debt_ratio": m.debt_ratio if m else None,
                "market_cap": m.market_cap if m else None,
                "dividend_yield_current": m.dividend_yield_current if m else None,
            },
        )

    async def execute_run(  # type: ignore[override]
        self,
        db: Session,
        provider: AIProvider,
        run: AIRun,
        stock: Stock,
        **_: Any,
    ) -> AIRun:
        """Walk the bracket round by round, persisting the final result.

        The input payload was already resolved during `queue_run`; we only
        need to (a) fan out per-match LLM calls and (b) update the existing
        running row with the aggregate result, total cost and duration.
        """
        payload = run.input_payload
        participants_raw = payload.get("participants", [])
        provider_name = getattr(provider, "name", provider.__class__.__name__.lower())
        provider_model = getattr(provider, "model", "unknown")

        if len(participants_raw) < 2:
            return self._finish_run(
                db,
                run,
                provider_name,
                provider_model,
                status="error",
                result_dict=None,
                error_text="Mindestens 2 Teilnehmer benötigt",
                total_cost=None,
                duration_ms=0,
            )

        # Pad to the next power of two with `None` byes; a bye automatically
        # advances its opponent without an LLM call.
        size = 1 << max(1, math.ceil(math.log2(len(participants_raw))))
        seeded: list[CompanyProfile | None] = [
            CompanyProfile(**p) for p in participants_raw
        ]
        seeded += [None] * (size - len(seeded))

        system_prompt = self.load_prompt().strip()
        schema = SingleMatch.model_json_schema()

        rounds: list[list[Match]] = []
        current: list[CompanyProfile | None] = seeded
        total_cost = 0.0
        cost_seen = False
        started = time.perf_counter()
        try:
            while len(current) > 1:
                next_round: list[CompanyProfile | None] = []
                this_round: list[Match] = []
                for i in range(0, len(current), 2):
                    a = current[i]
                    b = current[i + 1] if i + 1 < len(current) else None
                    if a is None and b is None:
                        next_round.append(None)
                        continue
                    if a is None:
                        next_round.append(b)
                        continue
                    if b is None:
                        next_round.append(a)
                        continue
                    match, cost = await self._run_match(
                        provider, system_prompt, schema, a, b
                    )
                    if cost is not None:
                        total_cost += cost
                        cost_seen = True
                    this_round.append(match)
                    next_round.append(a if match.winner == a.isin else b)
                rounds.append(this_round)
                current = next_round

            winner = next((p for p in current if p is not None), None)
            if winner is None:  # pragma: no cover - defensive
                raise RuntimeError("Kein Bracket-Sieger ermittelbar")
            winner_rationale = (
                rounds[-1][-1].rationale if rounds and rounds[-1] else ""
            )
            result = TournamentResult(
                rounds=rounds,
                winner_isin=winner.isin,
                winner_rationale=winner_rationale,
                summary=(
                    f"{winner.name} setzt sich in {len(rounds)} Runden gegen "
                    f"{len(participants_raw) - 1} Peers durch."
                ),
            )
            run_status = "done"
            error_text: str | None = None
            result_dict: dict[str, Any] | None = result.model_dump(mode="json")
        except Exception as exc:
            run_status = "error"
            error_text = str(exc) or exc.__class__.__name__
            result_dict = None

        duration_ms = int((time.perf_counter() - started) * 1000)
        return self._finish_run(
            db,
            run,
            provider_name,
            provider_model,
            status=run_status,
            result_dict=result_dict,
            error_text=error_text,
            total_cost=total_cost if cost_seen else None,
            duration_ms=duration_ms,
        )

    async def _run_match(
        self,
        provider: AIProvider,
        system_prompt: str,
        schema: dict[str, Any],
        a: CompanyProfile,
        b: CompanyProfile,
    ) -> tuple[Match, float | None]:
        user_payload = {"a": a.model_dump(), "b": b.model_dump()}
        user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)
        completion: CompletionResult = await provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            json_schema=schema,
        )
        single = SingleMatch.model_validate(completion.parsed)
        winner_isin = a.isin if single.winner == "a" else b.isin
        # Make sure all categories are present even if the LLM omits one.
        scores: dict[str, MatchScore] = {}
        for category in TOURNAMENT_CATEGORIES:
            score = single.category_scores.get(category) or MatchScore(a=2, b=2)
            scores[category] = score
        match = Match(
            a=a.isin,
            b=b.isin,
            category_scores=scores,
            winner=winner_isin,
            rationale=single.rationale,
        )
        return match, completion.estimated_cost

    def _finish_run(
        self,
        db: Session,
        run: AIRun,
        provider_name: str,
        provider_model: str,
        *,
        status: str,
        result_dict: dict[str, Any] | None,
        error_text: str | None,
        total_cost: float | None,
        duration_ms: int,
    ) -> AIRun:
        run.provider = provider_name
        run.model = provider_model
        run.status = status
        run.result_payload = result_dict
        run.error_text = error_text
        run.cost_estimate = total_cost
        run.duration_ms = duration_ms
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
