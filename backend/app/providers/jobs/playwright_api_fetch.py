"""Adapter: open the portal in Chromium, then call its private API.

Some portals (notably Nike) gate their API behind a ``__cf-bm`` /
``__nike_session`` cookie that is only set after the SPA has booted.
The HTTP-only ``json_post_path_int`` adapter therefore gets a 403 even
with a real browser ``User-Agent``. This adapter:

1. Navigates to ``portal_url`` so Cloudflare / the SPA bootstrap can
   set their cookies on the context.
2. Dismisses the cookie banner (best-effort).
3. Performs the API call with ``page.evaluate(fetch(...))`` so the
   browser context replays the freshly issued cookies.
4. Walks ``value_path`` (dot-separated) into the JSON response.

Settings:
* ``endpoint``    – required, absolute URL of the JSON endpoint.
* ``value_path``  – required, dotted path to the count int.
* ``payload``     – optional dict, sent as JSON body (default ``{}``).
* ``method``      – optional, ``GET`` or ``POST`` (default ``POST``).
* ``timeout_ms``  – optional, default 30000.
"""
from __future__ import annotations

import json
from typing import Any

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter
from app.providers.jobs.playwright_pool import PlaywrightPool, dismiss_cookie_banner

# Runs inside the page context. Receives [endpoint, method, payloadJson]
# so the Python side controls the verb. Returns the parsed JSON.
_FETCH_SCRIPT = """async ([endpoint, method, payloadStr]) => {
    const init = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    };
    if (method !== 'GET' && payloadStr) {
        init.body = payloadStr;
    }
    const response = await fetch(endpoint, init);
    if (!response.ok) {
        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
    }
    return await response.json();
}"""


class PlaywrightApiFetchAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}

        endpoint = settings.get("endpoint")
        if not endpoint:
            raise AdapterError(f"job_source {source.id}: missing settings.endpoint")
        value_path = settings.get("value_path")
        if not value_path:
            raise AdapterError(f"job_source {source.id}: missing settings.value_path")

        payload = settings.get("payload", {}) or {}
        method = str(settings.get("method", "POST")).upper()
        timeout_ms = int(settings.get("timeout_ms", 30000))

        if method not in {"GET", "POST"}:
            raise AdapterError(
                f"job_source {source.id}: unsupported method {method!r} "
                "(GET or POST only)"
            )

        pool = await PlaywrightPool.get_instance()
        async with pool.acquire_page() as page:
            # The portal page itself is not what we care about — we just
            # need its cookies. ``domcontentloaded`` is enough; we don't
            # wait for every analytics tracker to settle.
            await page.goto(
                source.portal_url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            await page.wait_for_timeout(2000)
            await dismiss_cookie_banner(page)

            payload_str = json.dumps(payload)
            try:
                result = await page.evaluate(
                    _FETCH_SCRIPT,
                    [endpoint, method, payload_str],
                )
            except Exception as exc:
                raise AdapterError(
                    f"job_source {source.id}: in-browser fetch failed: {exc}"
                ) from exc

            value: Any = result
            for part in value_path.split("."):
                if not isinstance(value, dict) or part not in value:
                    raise AdapterError(
                        f"job_source {source.id}: value path "
                        f"{value_path!r} not found in response"
                    )
                value = value[part]

            try:
                count = int(value)
            except (TypeError, ValueError) as exc:
                raise AdapterError(
                    f"job_source {source.id}: value at {value_path!r} "
                    f"is not an int (got {value!r})"
                ) from exc

            return count, {
                "endpoint": endpoint,
                "value_path": value_path,
                "method": method,
            }
