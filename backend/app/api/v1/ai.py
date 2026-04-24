"""AI agent endpoints.

The router exposes the agent registry to the frontend:

* `GET /ai/agents` – lists every registered agent including its JSON output schema.
* `GET /ai/agents/{id}/prompt` – serves the static prompt template (read-only).
* `POST /ai/agents/{id}/run/{isin}` – synchronously executes the agent and
  persists an `AIRun` row.
* `GET /ai/agents/{id}/runs/{isin}` – history of past runs for a single
  stock + agent combination.
* `GET /ai/runs/{run_id}` – fetches one persisted run with its full payload.
* `POST /ai/test` – probes the configured provider (`provider.ping()`).
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.agents import get_agent, list_agents
from app.api.deps import csrf_guard, get_current_user, require_admin
from app.db.session import get_db
from app.models.ai_run import AIRun
from app.models.settings import AppSettings
from app.models.stock import Stock
from app.schemas.ai import AgentInfoOut, AgentRunRequest, AIRunOut
from app.services.provider_factory import build_ai_provider
from app.services.run_status_service import humanize_error

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/agents", response_model=list[AgentInfoOut])
def get_agents(_: dict = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "output_schema": agent.output_schema.model_json_schema(),
        }
        for agent in list_agents()
    ]


@router.get("/agents/{agent_id}/prompt", response_class=PlainTextResponse)
def get_agent_prompt(agent_id: str, _: dict = Depends(get_current_user)) -> str:
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.load_prompt()


@router.post(
    "/agents/{agent_id}/run/{isin}",
    response_model=AIRunOut,
    dependencies=[Depends(csrf_guard)],
)
async def run_agent(
    agent_id: str,
    isin: str,
    payload: AgentRunRequest | None = None,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIRun:
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    stock = db.get(Stock, isin.upper())
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    settings_row = db.get(AppSettings, 1) or AppSettings(id=1)
    provider = build_ai_provider(settings_row)
    kwargs: dict = {}
    if payload is not None and payload.peers is not None:
        kwargs["peers"] = payload.peers
    return await agent.run(db, provider, stock, **kwargs)


@router.get(
    "/agents/{agent_id}/runs/{isin}",
    response_model=list[AIRunOut],
)
def list_agent_runs(
    agent_id: str,
    isin: str,
    limit: int = Query(default=10, ge=1, le=100),
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AIRun]:
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return (
        db.query(AIRun)
        .filter(AIRun.agent_id == agent_id, AIRun.isin == isin.upper())
        .order_by(AIRun.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/runs/{run_id}", response_model=AIRunOut)
def get_run(
    run_id: int,
    _: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIRun:
    run = db.get(AIRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/test", dependencies=[Depends(csrf_guard)])
async def test_ai_connection(
    _: dict = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Probe the configured AI provider with a minimal `ping()` request."""
    row = db.get(AppSettings, 1) or AppSettings(id=1)
    provider = build_ai_provider(row)
    started = time.perf_counter()
    try:
        await provider.ping()
        return {
            "ok": True,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "provider": row.ai_provider,
            "model": row.ai_model,
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": humanize_error(exc),
            "provider": row.ai_provider,
            "model": row.ai_model,
        }
