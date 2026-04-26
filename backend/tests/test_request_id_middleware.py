"""Verifies the X-Request-ID middleware round-trip.

The middleware should:
* honour an inbound `X-Request-ID` (so a frontend correlation id stays
  stable across the boundary),
* generate a fresh one when the client doesn't supply it,
* echo the resolved id in the response header.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER
from app.main import app


def test_request_id_is_generated_when_missing() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    rid = resp.headers.get(REQUEST_ID_HEADER)
    assert rid and len(rid) >= 16  # uuid4 hex is 32 chars; allow trimmed values


def test_request_id_is_preserved_when_supplied() -> None:
    client = TestClient(app)
    resp = client.get(
        "/api/v1/health",
        headers={REQUEST_ID_HEADER: "trace-abc-123"},
    )
    assert resp.status_code == 200
    assert resp.headers.get(REQUEST_ID_HEADER) == "trace-abc-123"
