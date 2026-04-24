"""Tests for the AI provider strategy classes.

We never hit OpenAI or a local Ollama instance in CI: the fallback path is
exercised by omitting the API key, and HTTP errors are simulated by pointing
the provider at an unreachable endpoint.
"""
from __future__ import annotations

import asyncio

from app.providers.ai.ollama_provider import OllamaProvider
from app.providers.ai.openai_provider import OpenAIProvider


def test_openai_without_key_returns_fallback() -> None:
    provider = OpenAIProvider(endpoint="https://invalid.example", model="gpt-4o-mini", api_key=None)
    payload = {"burggraben": True, "current_price": 100.0, "dcf_discount_pct": -0.1}
    result = asyncio.run(provider.evaluate(payload))

    assert result.is_fallback is True
    assert result.recommendation in {"buy", "risk_buy"}
    assert result.fair_value_dcf == 112.0
    assert result.fair_value_nav == 106.0
    assert result.estimated_cost == 0.0


def test_openai_falls_back_when_endpoint_unreachable() -> None:
    """A network error must transparently degrade to the heuristic."""
    provider = OpenAIProvider(
        endpoint="http://127.0.0.1:1/does-not-exist",
        model="gpt-4o-mini",
        api_key="sk-fake",
    )
    payload = {"burggraben": False, "current_price": 50.0, "dcf_discount_pct": 0.2}
    result = asyncio.run(provider.evaluate(payload))
    assert result.is_fallback is True


def test_ollama_falls_back_when_endpoint_unreachable() -> None:
    provider = OllamaProvider(endpoint="http://127.0.0.1:1/does-not-exist", model="llama3")
    result = asyncio.run(provider.evaluate({"current_price": 200.0}))
    assert result.is_fallback is True
    assert result.fair_value_dcf > 0
