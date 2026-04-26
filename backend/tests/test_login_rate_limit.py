"""Verifies that POST /auth/login is throttled per source IP.

The limiter is globally disabled in tests (see `conftest.py`) so unrelated
test cases can hit the login endpoint freely. This test toggles the limiter
back on, resets its in-memory storage, and asserts that the 6th attempt
within a minute is rejected with HTTP 429.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app


@pytest.fixture()
def enabled_limiter():
    previous = limiter.enabled
    limiter.enabled = True
    # Wipe any state left behind by other tests so we get a fresh window.
    limiter.reset()
    try:
        yield limiter
    finally:
        limiter.enabled = previous
        limiter.reset()


def test_login_returns_429_after_burst(enabled_limiter) -> None:
    client = TestClient(app)
    payload = {"username": "admin", "password": "wrong-on-purpose"}

    # First five attempts hit the auth path and return 401 for bad creds.
    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401, resp.text

    # The sixth attempt within the same minute must be throttled before
    # reaching the credential check.
    throttled = client.post("/api/v1/auth/login", json=payload)
    assert throttled.status_code == 429
    assert "Zu viele Anfragen" in throttled.json()["detail"]
