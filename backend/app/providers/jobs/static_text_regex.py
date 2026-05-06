"""Adapter: GET static HTML and extract a job count via regex.

Used for portals that server-render the result counter directly into the HTML
(e.g. Attrax/Phenom-based sites like AbbVie). No browser needed.

Steps:
1. GET ``portal_url`` with httpx.
2. Run ``regex_pattern`` against the raw HTML text.
3. Extract capture group 1, strip thousands separators, return as int.

Settings:
* ``regex_pattern``    – required, capture group 1 holds the number.
* ``timeout_seconds``  – optional, default 20.
* ``headers``          – optional extra request headers dict.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class StaticTextRegexAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}

        pattern = settings.get("regex_pattern")
        if not pattern:
            raise AdapterError(
                f"job_source {source.id}: missing settings.regex_pattern"
            )

        timeout_seconds = float(settings.get("timeout_seconds", 20))
        extra_headers: dict[str, str] = settings.get("headers") or {}
        headers = {"User-Agent": _DEFAULT_UA, **extra_headers}

        async with httpx.AsyncClient(
            timeout=timeout_seconds, follow_redirects=True, headers=headers
        ) as client:
            response = await client.get(source.portal_url)
            response.raise_for_status()

        html = response.text
        match = re.search(pattern, html, re.IGNORECASE)

        if match is None:
            preview = html[:500].replace("\n", " ").replace("\r", "")
            raise AdapterError(
                f"job_source {source.id}: regex did not match. "
                f"url={response.url} preview={preview!r}"
            )

        # Prefer the first non-None capture group; fall back to full match.
        count_str: str | None = None
        for group in match.groups():
            if group is not None:
                count_str = group
                break
        if count_str is None:
            count_str = match.group(0)

        # Strip locale-specific thousands separators (en: 1,234  de: 1.234  fr: 1 234).
        normalized = count_str.replace(",", "").replace(".", "").replace("\u00a0", "").replace(" ", "")
        try:
            count = int(normalized)
        except ValueError as exc:
            raise AdapterError(
                f"job_source {source.id}: matched text {count_str!r} is not an integer"
            ) from exc

        return count, {
            "pattern": pattern,
            "matched_text": match.group(0),
            "url": str(response.url),
        }
