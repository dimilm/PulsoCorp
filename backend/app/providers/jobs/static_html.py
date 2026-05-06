"""Adapter: count CSS matches on a static HTML response.

Settings:
* ``count_selector``  – required, CSS selector applied with BeautifulSoup.
* ``timeout_seconds`` – optional, default 20.
"""
from __future__ import annotations

from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter


class StaticHtmlAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}
        selector = settings.get("count_selector")
        if not selector:
            raise AdapterError(f"job_source {source.id}: missing settings.count_selector")

        timeout_seconds = float(settings.get("timeout_seconds", 20))
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(source.portal_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        matches = soup.select(selector)
        return len(matches), {"selector": selector, "url": str(response.url)}
