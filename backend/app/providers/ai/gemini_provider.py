"""Google Gemini provider using the generative-language REST API.

The endpoint is treated as a base URL (e.g.
``https://generativelanguage.googleapis.com/v1beta``); the full URL is
composed as ``{endpoint}/models/{model}:generateContent`` per request so the
user can switch models without re-saving the endpoint.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.providers.ai.base import AIProvider, CompletionResult
from app.providers.ai.pricing import estimate_cost


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, endpoint: str, model: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ValueError("Kein API-Key hinterlegt")
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

    def _url(self) -> str:
        return f"{self.endpoint}/models/{self.model}:generateContent"

    async def ping(self) -> None:
        body = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(self._url(), headers=self._headers(), json=body)
            response.raise_for_status()

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        # Gemini has no dedicated "system" role; we prepend it as the first
        # user turn separated by two newlines, which the API treats as
        # high-priority instructions in practice.
        combined = f"{system_prompt}\n\n{user_prompt}"
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": combined}]}],
            "generationConfig": {"temperature": temperature},
        }
        if json_schema is not None:
            body["generationConfig"]["responseMimeType"] = "application/json"

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self._url(), headers=self._headers(), json=body)
            response.raise_for_status()
            data = response.json()

        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata") or {}
        input_tokens = usage.get("promptTokenCount")
        output_tokens = usage.get("candidatesTokenCount")

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
