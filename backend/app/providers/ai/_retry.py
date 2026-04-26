"""Shared retry helper for AI provider HTTP calls.

Preview/flash LLMs at Google and OpenAI return ``429`` (rate limit) and
``5xx`` (overload, transient outage) more often than stable tiers. Without
retries a single such response would crash multi-call agents like the peer
tournament — which makes up to 7 sequential calls per run — even though the
upstream service almost always recovers within a couple of seconds.

The helper retries on a closed set of "transient" conditions only:

* network errors (``httpx.TransportError`` covers timeouts, DNS failures,
  connection resets), and
* HTTP status ``408`` (request timeout), ``425`` (too early), ``429`` (rate
  limited), ``500`` (internal), ``502`` (bad gateway), ``503`` (service
  unavailable), ``504`` (gateway timeout).

Any other ``4xx`` (auth, bad request, ...) is raised immediately because
re-trying would not change the outcome.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_BACKOFF_FACTOR = 2.0


async def post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: Any | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> httpx.Response:
    """POST ``json`` to ``url`` with exponential backoff on transient errors.

    Returns the successful ``httpx.Response`` (status checked via
    ``raise_for_status``). Raises the last encountered exception if all
    attempts are exhausted.
    """
    delay = initial_delay
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.post(url, headers=headers, json=json)
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise
            logger.warning(
                "AI provider transport error (attempt %d/%d): %s — retrying in %.1fs",
                attempt,
                max_attempts,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
            continue

        if response.status_code in _RETRYABLE_STATUSES and attempt < max_attempts:
            logger.warning(
                "AI provider returned %d (attempt %d/%d) — retrying in %.1fs",
                response.status_code,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor
            continue

        response.raise_for_status()
        return response

    # Defensive: loop above always either returns or raises, but mypy/pyright
    # need an explicit fallthrough for the "all retryable" path.
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("post_with_retry exhausted retries without an exception")
