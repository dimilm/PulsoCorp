"""Latest-AI-run lookup helpers used by the watchlist table.

The watchlist needs a compact summary of the most recent successful run per
`(isin, agent_id)` pair so it can render the four mini-pills inline in the
table. We deliberately keep this module separate from `stock_service` so the
two concerns stay independently testable: one owns the SQL window-query, the
other glues the result onto the existing `StockOut` payload.

Tournament results are only meaningful when the stock was the bracket's main
candidate (`input_payload.main_isin == isin`), so the verdict is filtered in
Python after the SQL stage — SQLite's JSON path queries are too fragmented to
rely on for that.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ai_run import AIRun

# Agents that can show a per-stock verdict. Hard-coded instead of imported
# from `app.agents` to avoid a circular import — `stock_service` consumes us
# and is itself imported by the tournament agent. The set is small and
# stable; if a new agent gets added it just stays invisible in the watchlist
# until its id is registered here.
_KNOWN_AGENT_IDS: frozenset[str] = frozenset(
    {"fisher", "redflag", "scenario", "tournament"}
)


def latest_done_runs_by_isin(
    db: Session, isins: list[str]
) -> dict[str, dict[str, AIRun]]:
    """Return the newest `status="done"` `AIRun` per `(isin, agent_id)`.

    Result shape: `{isin: {agent_id: AIRun}}`. The outer dict only contains
    keys for ISINs that actually have at least one matching run; callers
    treat missing keys as "no AI runs yet".
    """
    if not isins:
        return {}

    rn = (
        func.row_number()
        .over(
            partition_by=(AIRun.isin, AIRun.agent_id),
            order_by=AIRun.created_at.desc(),
        )
        .label("rn")
    )
    sub = (
        select(AIRun.id, rn)
        .where(AIRun.isin.in_(isins), AIRun.status == "done")
        .subquery()
    )
    rows = (
        db.execute(
            select(AIRun)
            .join(sub, AIRun.id == sub.c.id)
            .where(sub.c.rn == 1)
        )
        .scalars()
        .all()
    )

    out: dict[str, dict[str, AIRun]] = {}
    for run in rows:
        out.setdefault(run.isin, {})[run.agent_id] = run
    return out


def summarize_run(run: AIRun) -> dict[str, Any] | None:
    """Reduce an `AIRun.result_payload` to the few fields the pills need.

    Returns `None` if the run cannot meaningfully be summarized (missing
    payload, tournament where this stock was not the main candidate, …).
    The watchlist treats `None` as "do not render a pill for this agent".
    """
    if run.status != "done" or run.result_payload is None:
        return None

    payload = run.result_payload
    agent_id = run.agent_id

    if agent_id == "fisher":
        score = payload.get("total_score")
        verdict = payload.get("verdict")
        if score is None or verdict is None:
            return None
        return {"score": int(score), "verdict": str(verdict)}

    if agent_id == "redflag":
        overall = payload.get("overall_risk")
        flags = payload.get("flags") or []
        if overall is None:
            return None
        return {"overall_risk": str(overall), "flag_count": len(flags)}

    if agent_id == "scenario":
        ret = payload.get("expected_return_pct")
        if ret is None:
            return None
        return {"expected_return_pct": float(ret)}

    if agent_id == "tournament":
        # Only surface a pill when this stock was the bracket's main
        # candidate; any other tournament merely *contains* the stock as a
        # peer, which would be misleading on the per-row pill.
        main_isin = (run.input_payload or {}).get("main_isin")
        if main_isin != run.isin:
            return None
        winner = payload.get("winner_isin")
        participants = (run.input_payload or {}).get("participants") or []
        peer_count = max(0, len(participants) - 1)
        if winner is None:
            return None
        return {
            "is_winner": winner == run.isin,
            "winner_isin": str(winner),
            "peer_count": peer_count,
        }

    return None


def build_latest_run_summaries(
    db: Session, isins: list[str]
) -> dict[str, dict[str, dict[str, Any]]]:
    """High-level helper used by the stock service.

    Returns `{isin: {agent_id: {agent_id, created_at, model, summary}}}`,
    ready to be folded into the `StockOut.latest_ai_runs` field.
    """
    raw = latest_done_runs_by_isin(db, isins)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for isin, by_agent in raw.items():
        per_agent: dict[str, dict[str, Any]] = {}
        for agent_id, run in by_agent.items():
            if agent_id not in _KNOWN_AGENT_IDS:
                continue
            summary = summarize_run(run)
            if summary is None:
                continue
            per_agent[agent_id] = {
                "agent_id": agent_id,
                "created_at": run.created_at,
                "model": run.model,
                "summary": summary,
            }
        if per_agent:
            out[isin] = per_agent
    return out
