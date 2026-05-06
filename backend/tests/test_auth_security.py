"""Negative auth/CSRF tests covering the hardening done in Etappe B."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def _login(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    return resp.json()["csrf_token"]


def test_login_sets_both_session_cookies() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "changeme"})
    assert resp.status_code == 200
    cookies = {c.name: c for c in client.cookies.jar}
    assert settings.auth_cookie_name in cookies
    assert settings.csrf_cookie_name in cookies
    # The CSRF cookie must be readable from JS, the auth cookie must not.
    set_cookie_headers = resp.headers.get_list("set-cookie")
    auth_header = next(h for h in set_cookie_headers if h.startswith(settings.auth_cookie_name + "="))
    csrf_header = next(h for h in set_cookie_headers if h.startswith(settings.csrf_cookie_name + "="))
    assert "HttpOnly" in auth_header
    assert "HttpOnly" not in csrf_header


def test_me_does_not_rotate_csrf_token() -> None:
    client = TestClient(app)
    csrf = _login(client)
    initial_cookie = client.cookies.get(settings.csrf_cookie_name)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    # New schema returns no csrf_token, and the cookie value must not change.
    assert body.get("csrf_token") in (None, csrf)
    assert client.cookies.get(settings.csrf_cookie_name) == initial_cookie


def test_csrf_required_for_mutations() -> None:
    client = TestClient(app)
    _login(client)
    payload = {
        "isin": "US0000099999",
        "name": "CSRF Guard Stock",
        "sector": "Tech",
        "currency": "USD",
        "tranches": 0,
    }
    # Missing header -> 403
    no_header = client.post("/api/v1/stocks", json=payload)
    assert no_header.status_code == 403

    # Wrong header -> 403 (constant-time compare)
    wrong_header = client.post("/api/v1/stocks", json=payload, headers={"X-CSRF-Token": "totally-wrong"})
    assert wrong_header.status_code == 403


def test_protected_endpoint_requires_auth_cookie() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_logout_clears_cookies() -> None:
    client = TestClient(app)
    _login(client)
    assert client.cookies.get(settings.auth_cookie_name)
    client.post("/api/v1/auth/logout")
    # delete_cookie sends a Set-Cookie with Max-Age=0; the client may keep an
    # empty placeholder, so accept both "missing" and "blank".
    assert not client.cookies.get(settings.auth_cookie_name)
    assert not client.cookies.get(settings.csrf_cookie_name)
