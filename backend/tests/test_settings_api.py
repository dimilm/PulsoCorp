"""Tests for `GET/PUT /api/v1/settings`.

Focus on the `ai_api_key_set` flag added so the Settings UI can show
"Schlüssel hinterlegt" without ever exposing the encrypted value itself.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.settings import AppSettings


def _login(client: TestClient, username: str = "admin", password: str = "changeme") -> str:
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


def _reset_api_key() -> None:
    """Strip any stored key so each test starts from a clean state."""
    db = SessionLocal()
    try:
        row = db.get(AppSettings, 1)
        if row and row.ai_api_key_encrypted:
            row.ai_api_key_encrypted = None
            db.add(row)
            db.commit()
    finally:
        db.close()


def test_get_settings_reports_no_key_by_default() -> None:
    _reset_api_key()
    client = TestClient(app)
    _login(client)

    resp = client.get("/api/v1/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_api_key_set"] is False
    assert "ai_api_key" not in body
    assert "ai_api_key_encrypted" not in body


def test_put_settings_with_key_sets_flag() -> None:
    _reset_api_key()
    client = TestClient(app)
    csrf = _login(client)

    resp = client.put(
        "/api/v1/settings",
        headers={"X-CSRF-Token": csrf},
        json={"ai_api_key": "sk-test-1234567890"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_api_key_set"] is True
    assert "ai_api_key" not in body

    resp2 = client.get("/api/v1/settings")
    assert resp2.json()["ai_api_key_set"] is True


def test_put_settings_without_key_leaves_existing_key_intact() -> None:
    _reset_api_key()
    client = TestClient(app)
    csrf = _login(client)

    client.put("/api/v1/settings", headers={"X-CSRF-Token": csrf}, json={"ai_api_key": "sk-keep-me"})
    resp = client.put(
        "/api/v1/settings",
        headers={"X-CSRF-Token": csrf},
        json={"update_hour": 7, "update_minute": 15},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["update_hour"] == 7
    assert body["update_minute"] == 15
    assert body["ai_api_key_set"] is True
