"""Ollama provider (self-hosted LLM via the local /api/generate endpoint).

The endpoint is configured pointing at ``/api/generate``. For health checks
we derive the server root and call ``/api/tags`` instead because it is the
cheapest authenticated endpoint that confirms the daemon is up.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.providers.ai.base import AIProvider, CompletionResult


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, endpoint: str, model: str) -> None:
        self.endpoint = endpoint
        self.model = model

    async def ping(self) -> None:
        endpoint = self.endpoint or "http://localhost:11434/api/generate"
        base = endpoint.split("/api/", 1)[0] if "/api/" in endpoint else endpoint.rstrip("/")
        url = f"{base}/api/tags"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_schema is not None:
            body["format"] = "json"

        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(self.endpoint, json=body)
            response.raise_for_status()
            data = response.json()

        raw_text = data.get("response", "")
        # Ollama exposes total token counts under prompt_eval_count / eval_count.
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")

        if json_schema is not None:
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Provider lieferte kein valides JSON: {exc}") from exc
        else:
            parsed = {"text": raw_text}

        return CompletionResult(
            parsed=parsed,
            raw_text=raw_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
        )
