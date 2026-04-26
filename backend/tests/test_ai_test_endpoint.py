"""Tests for `POST /api/v1/ai/test`.

The endpoint must never raise — failures are mapped to `{ok: false, error}`
so the Settings page can render them inline. We override the AI-provider
dependency so no real network call ever happens in CI.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_ai_provider
from app.core.config import settings
from app.main import app
from app.providers.ai.base import AIProvider


def _login(client: TestClient, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


class _OkProvider(AIProvider):
    async def ping(self) -> None:
        return None


class _FailProvider(AIProvider):
    async def ping(self) -> None:
        raise RuntimeError("connection refused")


def test_ai_test_returns_ok_when_provider_pings() -> None:
    client = TestClient(app)
    csrf = _login(client)
    app.dependency_overrides[get_ai_provider] = lambda: _OkProvider()
    try:
        resp = client.post("/api/v1/ai/test", headers={"X-CSRF-Token": csrf})
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "latency_ms" in body
    assert body["provider"] in {"openai", "gemini", "ollama"}
    assert isinstance(body["model"], str) and body["model"]


def test_ai_test_returns_humanised_error_on_failure() -> None:
    client = TestClient(app)
    csrf = _login(client)
    app.dependency_overrides[get_ai_provider] = lambda: _FailProvider()
    try:
        resp = client.post("/api/v1/ai/test", headers={"X-CSRF-Token": csrf})
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    # `humanize_error` rewrites "connection refused" → "Verbindungsfehler".
    assert body["error"] == "Verbindungsfehler"


def test_ai_test_requires_csrf_token() -> None:
    client = TestClient(app)
    _login(client)
    resp = client.post("/api/v1/ai/test")
    assert resp.status_code == 403


def test_ai_test_requires_auth() -> None:
    """Drop only the auth cookie so CSRF stays valid and `require_admin` runs."""
    client = TestClient(app)
    csrf = _login(client)
    client.cookies.delete(settings.auth_cookie_name)
    resp = client.post("/api/v1/ai/test", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 401
