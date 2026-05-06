"""Adapter: GET a JSON document and count the items in an array field.

Settings:
* ``endpoint``        – required URL.
* ``array_field``     – required key whose value is a list (e.g. ``jobs``).
* ``params``          – optional dict of query parameters.
* ``headers``         – optional dict of request headers.
* ``timeout_seconds`` – optional, default 20.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter


class JsonGetArrayCountAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}
        endpoint = settings.get("endpoint")
        array_field = settings.get("array_field", "jobs")
        timeout_seconds = float(settings.get("timeout_seconds", 20))
        headers = settings.get("headers", {})
        params = settings.get("params")

        if not endpoint:
            raise AdapterError(f"job_source {source.id}: missing settings.endpoint")
        if not isinstance(array_field, str) or not array_field:
            raise AdapterError(
                f"job_source {source.id}: settings.array_field must be a non-empty string"
            )
        if params is not None and not isinstance(params, dict):
            raise AdapterError(
                f"job_source {source.id}: settings.params must be an object when provided"
            )

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            raise AdapterError(f"job_source {source.id}: response body is not a JSON object")

        items = data.get(array_field)
        if not isinstance(items, list):
            raise AdapterError(
                f"job_source {source.id}: field '{array_field}' missing or not a list"
            )

        return len(items), {"endpoint": endpoint, "array_field": array_field, "items": len(items)}
