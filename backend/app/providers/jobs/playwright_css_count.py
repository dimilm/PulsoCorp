"""Adapter: count DOM matches of a CSS selector via Playwright.

Useful when the portal does not expose a numeric counter but renders one
``<li>`` per job. Pagination is NOT followed — the selector must match
the *full* result set on a single page (typically by setting a
"per_page=200" query param in ``portal_url``).

Settings:
* ``count_selector``    – required, CSS selector counted via ``locator.count``.
* ``wait_for_selector`` – optional, defaults to ``count_selector``.
* ``timeout_ms``        – optional, default 30000.
"""
from __future__ import annotations

from typing import Any

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter
from app.providers.jobs.playwright_pool import PlaywrightPool, dismiss_cookie_banner


class PlaywrightCssCountAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}

        count_selector = settings.get("count_selector")
        if not count_selector:
            raise AdapterError(
                f"job_source {source.id}: missing settings.count_selector"
            )
        wait_selector = settings.get("wait_for_selector", count_selector)
        timeout_ms = int(settings.get("timeout_ms", 30000))

        pool = await PlaywrightPool.get_instance()
        async with pool.acquire_page() as page:
            await page.goto(source.portal_url, wait_until="networkidle", timeout=timeout_ms)
            await dismiss_cookie_banner(page)

            await page.wait_for_selector(wait_selector, state="attached", timeout=timeout_ms)
            # SPA result lists frequently mount in two passes — first the
            # placeholder skeletons, then the real cards. Wait a bit so
            # we count the final state instead of skeleton rows.
            await page.wait_for_timeout(2000)

            count = await page.locator(count_selector).count()
            return count, {
                "selector": count_selector,
                "wait_for_selector": wait_selector,
            }
