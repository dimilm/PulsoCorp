"""Base contract for the career-portal scrape adapters.

Mirrors the shape that ``11_JobCounter`` used so the existing scraper logic
ports over with minimal changes. The only difference is that we operate on
``JobSource`` ORM rows (with a JSON ``adapter_settings`` column) instead of
the standalone YAML-backed ``Company`` dataclass.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.job_source import JobSource


class AdapterError(RuntimeError):
    """Raised by adapters on configuration or fetch failures."""


class BaseJobAdapter(ABC):
    @abstractmethod
    async def fetch_job_count(self, source: JobSource) -> tuple[int, dict[str, Any]]:
        """Return (count, raw_meta) for the given source.

        Implementations must raise ``AdapterError`` on configuration mistakes
        and may propagate any networking exception unchanged so the retry
        layer in ``jobs_service`` can decide whether to retry.
        """
        raise NotImplementedError
