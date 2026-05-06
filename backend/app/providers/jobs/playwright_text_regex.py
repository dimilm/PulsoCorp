"""Adapter: open the page in Chromium and extract a count via regex.

Used for portals that render the result count client-side (Boeing, TUI,
Carnival, UnitedHealth in the legacy seed). The adapter:

1. Navigates to ``portal_url`` with ``networkidle``.
2. Tries to dismiss a cookie banner (best-effort).
3. Waits for ``wait_for_selector`` to attach, then for an extra 3 s so
   the JS-rendered count has actually settled.
4. Runs ``regex_pattern`` first against the raw HTML, then against
   ``document.body.innerText`` as a fallback (some sites render the
   number into Shadow DOM / canvas-rich layouts where the raw HTML
   only carries placeholders).
5. Strips thousands separators from the captured group and returns it.

Settings:
* ``wait_for_selector`` – required.
* ``regex_pattern``     – required, capture group 1 holds the number.
* ``timeout_ms``        – optional, default 30000.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter
from app.providers.jobs.playwright_pool import PlaywrightPool, dismiss_cookie_banner


class PlaywrightTextRegexAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}

        wait_selector = settings.get("wait_for_selector")
        if not wait_selector:
            raise AdapterError(
                f"job_source {source.id}: missing settings.wait_for_selector"
            )
        pattern = settings.get("regex_pattern")
        if not pattern:
            raise AdapterError(
                f"job_source {source.id}: missing settings.regex_pattern"
            )
        timeout_ms = int(settings.get("timeout_ms", 30000))

        pool = await PlaywrightPool.get_instance()
        async with pool.acquire_page() as page:
            await page.goto(source.portal_url, wait_until="networkidle", timeout=timeout_ms)
            await dismiss_cookie_banner(page)

            await page.wait_for_selector(wait_selector, state="attached", timeout=timeout_ms)
            # The cookie click + DOM-attach can race the result counter,
            # so we give the SPA a generous settle window before we read.
            await page.wait_for_timeout(3000)

            html = await page.content()
            visible_text = await page.evaluate("() => document.body.innerText")

            match = re.search(pattern, html, re.IGNORECASE)
            if match is None:
                match = re.search(pattern, visible_text, re.IGNORECASE)

            if match is None:
                preview = visible_text[:500].replace("\n", " ").replace("\r", "")
                raise AdapterError(
                    f"job_source {source.id}: regex did not match. "
                    f"url={page.url} preview={preview!r}"
                )

            # Prefer the first capture group; fall back to the whole match
            # for patterns that use a non-capturing group around the count.
            count_str: str | None = None
            for group in match.groups():
                if group is not None:
                    count_str = group
                    break
            if count_str is None:
                count_str = match.group(0)

            # Strip every locale's thousands marker (en: 1,234, de: 1.234,
            # fr: 1 234) before casting to int.
            normalized = (
                count_str.replace(",", "").replace(".", "").replace(" ", "")
            )
            try:
                count = int(normalized)
            except ValueError as exc:
                raise AdapterError(
                    f"job_source {source.id}: matched text {count_str!r} "
                    "is not an integer"
                ) from exc

            return count, {
                "pattern": pattern,
                "matched_text": match.group(0),
            }
