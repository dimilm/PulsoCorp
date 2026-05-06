"""Adapter: POST a search payload and sum the per-facet ``count`` fields.

Used by SAP SuccessFactors-style portals (Ferrari, Volkswagen) where the
search API returns the available filter values with a per-bucket count, and
summing those buckets yields the total job count.

Settings:
* ``endpoint``        – required URL.
* ``payload``         – required JSON-serialisable dict body.
* ``facet_field``     – required, key inside ``facets.map`` (default ``country``).
* ``headers``         – optional, default ``content-type: application/json``.
* ``timeout_seconds`` – optional, default 20.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.models.job_source import JobSource
from app.providers.jobs.base import AdapterError, BaseJobAdapter


class JsonPostFacetSumAdapter(BaseJobAdapter):
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        settings = source.adapter_settings or {}
        endpoint = settings.get("endpoint")
        payload = settings.get("payload")
        facet_field = settings.get("facet_field", "country")
        timeout_seconds = float(settings.get("timeout_seconds", 20))
        headers = settings.get("headers", {"content-type": "application/json"})

        if not endpoint:
            raise AdapterError(f"job_source {source.id}: missing settings.endpoint")
        if not isinstance(payload, dict):
            raise AdapterError(f"job_source {source.id}: settings.payload must be an object")

        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        facets_map = ((data.get("facets") or {}).get("map") or {})
        field_values = facets_map.get(facet_field)
        if not isinstance(field_values, list):
            raise AdapterError(
                f"job_source {source.id}: facets.map.{facet_field} missing or not a list"
            )

        count = 0
        for item in field_values:
            if isinstance(item, dict):
                count += int(item.get("count", 0))

        return count, {
            "endpoint": endpoint,
            "facet_field": facet_field,
            "items": len(field_values),
        }
