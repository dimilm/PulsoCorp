"""Background execution helpers for AI agent runs.

The HTTP route `POST /ai/agents/{id}/run/{isin}` returns immediately after
queueing an `AIRun` row with `status="running"`. The actual LLM call is
scheduled via FastAPI's `BackgroundTasks` and resolved here on the same
event loop with a fresh DB session and a fresh provider, so the request
session can be closed in the meantime.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents import get_agent
from app.db.session import SessionLocal
from app.models.ai_run import AIRun
from app.models.settings import AppSettings
from app.models.stock import Stock
from app.services.provider_factory import build_ai_provider

logger = logging.getLogger(__name__)


async def execute_run_in_background(
    run_id: int,
    agent_id: str,
    kwargs: dict[str, Any] | None = None,
) -> None:
    """Resolve a queued `AIRun` row by performing the LLM call.

    Always opens its own `SessionLocal` so the original request session can
    be closed independently. On any failure the run is forced to
    `status="error"` so the UI's polling loop terminates instead of
    spinning forever on a dangling `running` row.
    """
    kwargs = dict(kwargs or {})
    db = SessionLocal()
    try:
        agent = get_agent(agent_id)
        run = db.get(AIRun, run_id)
        if agent is None or run is None:  # pragma: no cover - defensive
            logger.warning(
                "ai background task: missing agent=%s or run=%s", agent_id, run_id
            )
            if run is not None:
                run.status = "error"
                run.error_text = "Agent not registered"
                run.duration_ms = 0
                db.commit()
            return
        stock = db.get(Stock, run.isin)
        if stock is None:  # pragma: no cover - defensive
            run.status = "error"
            run.error_text = "Stock not found"
            run.duration_ms = 0
            db.commit()
            return
        settings_row = db.get(AppSettings, 1) or AppSettings(id=1)
        provider = build_ai_provider(settings_row)
        await agent.execute_run(db, provider, run, stock, **kwargs)
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("ai background task failed: %s", exc)
        run = db.get(AIRun, run_id)
        if run is not None and run.status == "running":
            run.status = "error"
            run.error_text = str(exc) or exc.__class__.__name__
            if run.duration_ms is None:
                run.duration_ms = 0
            db.commit()
    finally:
        db.close()
