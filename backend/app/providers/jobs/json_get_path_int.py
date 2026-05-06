"""Adapter: GET a JSON document and read an integer at a dotted path.

Settings:
* ``endpoint``        – required URL.
* ``value_path``      – required dotted path (e.g. ``refineSearch.totalHits``).
* ``params``          – optional dict of query parameters.
* ``headers``         – optional dict of request headers.
* ``timeout_seconds`` – optional, default 20.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter


class JsonGetPathIntAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}
        endpoint = settings.get("endpoint")
        value_path = settings.get("value_path")
        timeout_seconds = float(settings.get("timeout_seconds", 20))
        headers = settings.get("headers", {})
        params = settings.get("params")

        if not endpoint:
            raise AdapterError(f"job_source {source.id}: missing settings.endpoint")
        if not isinstance(value_path, str) or not value_path.strip():
            raise AdapterError(
                f"job_source {source.id}: settings.value_path must be a non-empty string"
            )
        if params is not None and not isinstance(params, dict):
            raise AdapterError(
                f"job_source {source.id}: settings.params must be an object when provided"
            )

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        value: Any = data
        for part in value_path.split("."):
            if not isinstance(value, dict) or part not in value:
                raise AdapterError(
                    f"job_source {source.id}: value path '{value_path}' not found"
                )
            value = value[part]

        try:
            count = int(value)
        except (TypeError, ValueError) as exc:
            raise AdapterError(
                f"job_source {source.id}: value at '{value_path}' is not an integer"
            ) from exc

        return count, {"endpoint": endpoint, "value_path": value_path}
