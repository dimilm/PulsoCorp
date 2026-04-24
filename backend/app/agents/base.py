"""Base class for AI agents.

An agent is a small object that:

1. Builds a JSON-friendly input payload from the local DB (`build_input`).
2. Renders its static prompt template (loaded from `prompt.md` next to the
   agent module) by substituting the payload as JSON.
3. Calls the configured LLM provider through the generic `complete()` API.
4. Validates the structured response with its Pydantic `output_schema`.
5. Persists an `AIRun` row capturing input, output, cost and status.

The persistence step is shared so all agents end up in the same history
table with the same shape.
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

    async def run(
        self,
        db: Session,
        provider: AIProvider,
        stock: Stock,
        **kwargs: Any,
    ) -> AIRun:
        """Execute the agent end-to-end and persist a single `AIRun` row."""
        payload = self.build_input(db, stock, **kwargs)
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

        duration_ms = int((time.perf_counter() - started) * 1000)
        run = AIRun(
            isin=stock.isin,
            agent_id=self.id,
            created_at=utcnow(),
            provider=provider_name,
            model=provider_model,
            status=status,
            input_payload=payload,
            result_payload=result_dict,
            error_text=error_text,
            cost_estimate=completion.estimated_cost if completion is not None else None,
            duration_ms=duration_ms,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
