"""Tests for the generic LLM provider strategy classes.

Tests stay offline – we mock httpx.AsyncClient so we never hit OpenAI,
Gemini or a local Ollama instance in CI.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.ollama_provider import OllamaProvider
from app.providers.ai.openai_provider import OpenAIProvider


def _mock_async_client(json_payload: dict[str, Any]) -> Any:
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_payload)

    async_client = MagicMock()
    async_client.post = AsyncMock(return_value=response)
    async_client.get = AsyncMock(return_value=response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=async_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, async_client


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


def test_openai_complete_returns_parsed_json_and_token_metadata() -> None:
    payload = {
        "choices": [{"message": {"content": json.dumps({"score": 7})}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }
    cm, _ = _mock_async_client(payload)
    provider = OpenAIProvider(endpoint="https://api.test", model="gpt-4o-mini", api_key="sk-key")

    with patch("app.providers.ai.openai_provider.httpx.AsyncClient", return_value=cm):
        result = asyncio.run(
            provider.complete("system", "user", json_schema={"type": "object"})
        )

    assert result.parsed == {"score": 7}
    assert result.input_tokens == 100
    assert result.output_tokens == 20
    assert result.estimated_cost is not None and result.estimated_cost > 0


def test_openai_complete_without_schema_wraps_text() -> None:
    payload = {
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1},
    }
    cm, _ = _mock_async_client(payload)
    provider = OpenAIProvider(endpoint="https://api.test", model="gpt-4o-mini", api_key="sk-key")

    with patch("app.providers.ai.openai_provider.httpx.AsyncClient", return_value=cm):
        result = asyncio.run(provider.complete("system", "user"))

    assert result.parsed == {"text": "hello"}
    assert result.raw_text == "hello"


def test_openai_ping_without_key_raises() -> None:
    provider = OpenAIProvider(endpoint="https://invalid.example", model="gpt-4o-mini", api_key=None)
    with pytest.raises(ValueError, match="API-Key"):
        asyncio.run(provider.ping())


def test_openai_ping_unreachable_endpoint_raises() -> None:
    provider = OpenAIProvider(
        endpoint="http://127.0.0.1:1/does-not-exist",
        model="gpt-4o-mini",
        api_key="sk-fake",
    )
    with pytest.raises(Exception):
        asyncio.run(provider.ping())


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def test_gemini_complete_returns_parsed_json() -> None:
    payload = {
        "candidates": [{"content": {"parts": [{"text": json.dumps({"verdict": "ok"})}]}}],
        "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 10},
    }
    cm, _ = _mock_async_client(payload)
    provider = GeminiProvider(
        endpoint="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-1.5-flash",
        api_key="fake-key",
    )

    with patch("app.providers.ai.gemini_provider.httpx.AsyncClient", return_value=cm):
        result = asyncio.run(
            provider.complete("system", "user", json_schema={"type": "object"})
        )

    assert result.parsed == {"verdict": "ok"}
    assert result.input_tokens == 50
    assert result.output_tokens == 10


def test_gemini_ping_without_key_raises() -> None:
    provider = GeminiProvider(
        endpoint="https://generativelanguage.googleapis.com/v1beta",
        model="gemini-1.5-flash",
        api_key=None,
    )
    with pytest.raises(ValueError, match="API-Key"):
        asyncio.run(provider.ping())


def test_gemini_ping_unreachable_endpoint_raises() -> None:
    provider = GeminiProvider(
        endpoint="http://127.0.0.1:1/does-not-exist",
        model="gemini-1.5-flash",
        api_key="fake-key",
    )
    with pytest.raises(Exception):
        asyncio.run(provider.ping())


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


def test_ollama_complete_returns_parsed_json() -> None:
    payload = {
        "response": json.dumps({"flag": "low"}),
        "prompt_eval_count": 30,
        "eval_count": 8,
    }
    cm, _ = _mock_async_client(payload)
    provider = OllamaProvider(endpoint="http://localhost:11434/api/generate", model="llama3")

    with patch("app.providers.ai.ollama_provider.httpx.AsyncClient", return_value=cm):
        result = asyncio.run(
            provider.complete("system", "user", json_schema={"type": "object"})
        )

    assert result.parsed == {"flag": "low"}
    assert result.input_tokens == 30
    assert result.output_tokens == 8
    assert result.estimated_cost == 0.0


def test_ollama_ping_unreachable_endpoint_raises() -> None:
    provider = OllamaProvider(endpoint="http://127.0.0.1:1/api/generate", model="llama3")
    with pytest.raises(Exception):
        asyncio.run(provider.ping())
