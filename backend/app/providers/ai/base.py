"""Generic LLM provider interface used by every AI agent.

The provider has zero domain knowledge: it takes a system + user prompt and an
optional JSON schema and returns the parsed response together with token/cost
metadata. All stock-specific prompting lives in `app.agents.*`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CompletionResult:
    parsed: dict[str, Any]
    raw_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None


class AIProvider:
    name: str = "base"

    async def ping(self) -> None:
        """Verify the provider is reachable and authorised.

        Implementations must perform a minimal real network call and *raise*
        on any failure (missing key, HTTP error, timeout). The settings test
        endpoint relies on the raised exception to render a meaningful error
        message, so swallowing failures here would defeat its purpose.
        """
        raise NotImplementedError

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.2,
    ) -> CompletionResult:
        """Send the prompt to the model and return parsed text or JSON.

        When `json_schema` is provided the implementation must request a
        JSON response and return the parsed object in `CompletionResult.parsed`.
        Without a schema, `parsed` falls back to ``{"text": raw_text}`` so
        callers always get a dict.
        """
        raise NotImplementedError
