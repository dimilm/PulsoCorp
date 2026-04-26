"""Per-IP rate limiter shared across the API.

We expose a single `Limiter` instance so it stays in sync with the
`SlowAPIMiddleware` mounted on the FastAPI app. Endpoints opt in via the
`@limiter.limit(...)` decorator (and the matching `request: Request`
parameter slowapi requires).

The limiter can be globally toggled via the `RATE_LIMIT_ENABLED` env var.
We default to "on" in production but the test suite turns it off so the
test client's fixed source IP does not exhaust the per-route quota across
unrelated test cases. The dedicated rate-limit test re-enables it locally.
"""
from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _rate_limit_enabled_default() -> bool:
    raw = os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


# Default policy is intentionally permissive so unrelated endpoints are not
# affected; specific routes (e.g. /auth/login) tighten the limit per-route.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    enabled=_rate_limit_enabled_default(),
)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Translate slowapi's exception into a friendly JSON 429 response."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Zu viele Anfragen ({exc.detail}). Bitte später erneut versuchen."},
    )
