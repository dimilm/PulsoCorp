"""OpenAI Chat Completions provider.

Generic LLM client – the agent layer is responsible for prompts. Failures
propagate so the calling agent can persist a `status="error"` AIRun row.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.providers.ai._retry import post_with_retry
from app.providers.ai.base import AIProvider, CompletionResult
from app.providers.ai.pricing import estimate_cost


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self, endpoint: str, model: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("Kein API-Key hinterlegt")
        return {"Authorization": f"Bearer {self.api_key}"}

    async def ping(self) -> None:
        body = {
            "model": self.model,
            "max_tokens": 1,
            "temperature": 0,
            "messages": [{"role": "user", "content": "ping"}],
        }
        async with httpx.AsyncClient(timeout=15) as client:
            await post_with_retry(client, self.endpoint, headers=self._headers(), json=body)

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_schema is not None:
            # We use `json_object` rather than `json_schema` so the same code
            # path works against legacy and self-hosted OpenAI-compatible APIs.
            body["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=120) as client:
            response = await post_with_retry(
                client, self.endpoint, headers=self._headers(), json=body
            )
            data = response.json()

        raw_text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

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
            estimated_cost=estimate_cost(self.name, self.model, input_tokens, output_tokens),
        )
