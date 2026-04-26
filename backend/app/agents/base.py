"""Base class for AI agents.

An agent is a small object that:

1. Builds a JSON-friendly input payload from the local DB (`build_input`).
2. Renders its static prompt template (loaded from `prompt.md` next to the
   agent module) by substituting the payload as JSON.
3. Calls the configured LLM provider through the generic `complete()` API.
4. Validates the structured response with its Pydantic `output_schema`.
5. Persists an `AIRun` row capturing input, output, cost and status.

Persistence is split into two phases so the API can fire-and-forget agents:

* `queue_run` synchronously writes a row with `status="running"` and the
  resolved input payload, so the UI immediately gets a row to poll.
* `execute_run` performs the actual LLM call (async) and updates the same
  row to `status="done"` (or `"error"`) once the result is available.

`run` is kept as the synchronous composition (`queue_run` + `execute_run`)
so existing callers (tests, the Tournament-Agent's nested matches, ad-hoc
CLI usage) keep working without changes.
"""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.ai_run import AIRun
from app.models.stock import Stock
from app.providers.ai.base import AIProvider, CompletionResult


class BaseAgent(ABC):
    id: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    prompt_path: ClassVar[Path]
    output_schema: ClassVar[type[BaseModel]]

    @abstractmethod
    def build_input(self, db: Session, stock: Stock, **kwargs: Any) -> dict[str, Any]:
        """Return the JSON-serialisable payload that gets fed to the LLM."""

    def load_prompt(self) -> str:
        """Return the raw prompt template as written in `prompt.md`.

        Exposed so the API can serve it verbatim for the "Prompt anzeigen"
        modal — the user may inspect the prompt but not edit it.
        """
        return self.prompt_path.read_text(encoding="utf-8")

    def render_prompt(self, payload: dict[str, Any]) -> tuple[str, str]:
        """Split the prompt template into (system, user) parts.

        We keep templates minimal: the file is treated as the *system* prompt
        (i.e. the persona + task definition) and the rendered payload becomes
        the *user* turn. Agents that need a different layout can override.
        """
        system_prompt = self.load_prompt().strip()
        user_prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        return system_prompt, user_prompt

    def parse_output(self, raw_parsed: dict[str, Any]) -> BaseModel:
        return self.output_schema.model_validate(raw_parsed)

    def queue_run(self, db: Session, stock: Stock, **kwargs: Any) -> AIRun:
        """Insert a `running` AIRun row and return it without calling the LLM.

        The provider is unknown at queue-time (it is built later in the
        background task with a fresh DB session), so we store sentinel
        `pending` values that get overwritten by `execute_run`.
        """
        payload = self.build_input(db, stock, **kwargs)
        run = AIRun(
            isin=stock.isin,
            agent_id=self.id,
            created_at=utcnow(),
            provider="pending",
            model="pending",
            status="running",
            input_payload=payload,
            result_payload=None,
            error_text=None,
            cost_estimate=None,
            duration_ms=None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    async def execute_run(
        self,
        db: Session,
        provider: AIProvider,
        run: AIRun,
        stock: Stock,
        **kwargs: Any,
    ) -> AIRun:
        """Execute the LLM call for an already-queued `running` row.

        Updates the existing row in place; safe to call from a background
        task with its own DB session. `kwargs` are ignored at this level —
        the input payload was already resolved during `queue_run`. Agents
        that need bracket-style nested calls (e.g. tournament) override
        this method and may use `kwargs` to access the original parameters.
        """
        payload = run.input_payload
        system_prompt, user_prompt = self.render_prompt(payload)
        schema = self.output_schema.model_json_schema()
        provider_name = getattr(provider, "name", provider.__class__.__name__.lower())
        provider_model = getattr(provider, "model", "unknown")

        started = time.perf_counter()
        result_dict: dict[str, Any] | None = None
        error_text: str | None = None
        completion: CompletionResult | None = None
        status = "done"
        try:
            completion = await provider.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_schema=schema,
            )
            parsed = self.parse_output(completion.parsed)
            result_dict = parsed.model_dump(mode="json")
        except Exception as exc:
            status = "error"
            error_text = str(exc) or exc.__class__.__name__

        run.provider = provider_name
        run.model = provider_model
        run.status = status
        run.result_payload = result_dict
        run.error_text = error_text
        run.cost_estimate = (
            completion.estimated_cost if completion is not None else None
        )
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    async def run(
        self,
        db: Session,
        provider: AIProvider,
        stock: Stock,
        **kwargs: Any,
    ) -> AIRun:
        """Execute the agent end-to-end and persist a single `AIRun` row.

        Convenience composition of `queue_run` + `execute_run` for callers
        that don't care about the queued/running intermediate state (tests,
        nested usage, scripts).
        """
        run = self.queue_run(db, stock, **kwargs)
        return await self.execute_run(db, provider, run, stock, **kwargs)
