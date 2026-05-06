"""Pydantic schemas for the career-portal job-source feature.

Mirrors the shape of `app.schemas.stock` for consistency: a `JobSourceBase`
holds the user-editable fields, `JobSourceCreate` adds the required pieces
that only matter on insert, and `JobSourceOut` augments the row with the
derived "latest snapshot + delta" view used by every list endpoint.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.providers.jobs import ALL_KNOWN_ADAPTERS

# We accept every known adapter name (httpx + Playwright) at the schema
# layer so configurations survive on a backend that does not have the
# Playwright extra installed. The runtime layer (`jobs_service`) then
# returns a precise error if the user tries to actually scrape with one
# of the Playwright types.
_ALLOWED_ADAPTER_TYPES = set(ALL_KNOWN_ADAPTERS)


def _validate_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("URL must not be empty")
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        raise ValueError("URL must start with http:// or https://")
    return stripped


class JobSourceBase(BaseModel):
    isin: str | None = Field(default=None, max_length=12)
    name: str = Field(min_length=1, max_length=128)
    portal_url: str
    adapter_type: str
    adapter_settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("portal_url", mode="before")
    @classmethod
    def _check_url(cls, value: str) -> str:
        validated = _validate_url(value)
        if validated is None:
            raise ValueError("portal_url is required")
        return validated

    @field_validator("adapter_type")
    @classmethod
    def _check_adapter(cls, value: str) -> str:
        if value not in _ALLOWED_ADAPTER_TYPES:
            raise ValueError(
                f"adapter_type must be one of {sorted(_ALLOWED_ADAPTER_TYPES)}"
            )
        return value

    @field_validator("isin", mode="before")
    @classmethod
    def _normalize_isin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip().upper()
        return cleaned or None


class JobSourceCreate(JobSourceBase):
    pass


class JobSourceUpdate(BaseModel):
    isin: str | None = None
    name: str | None = None
    portal_url: str | None = None
    adapter_type: str | None = None
    adapter_settings: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("portal_url", mode="before")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_url(value)

    @field_validator("adapter_type")
    @classmethod
    def _check_adapter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _ALLOWED_ADAPTER_TYPES:
            raise ValueError(
                f"adapter_type must be one of {sorted(_ALLOWED_ADAPTER_TYPES)}"
            )
        return value

    @field_validator("isin", mode="before")
    @classmethod
    def _normalize_isin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip().upper()
        return cleaned or None


class JobSourceOut(JobSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    latest_count: int | None = None
    latest_snapshot_date: date | None = None
    delta_7d: int | None = None
    delta_30d: int | None = None

    model_config = ConfigDict(from_attributes=True)


class JobSnapshotOut(BaseModel):
    id: int
    job_source_id: int
    snapshot_date: date
    jobs_count: int
    recorded_at: datetime
    run_id: int | None = None
    raw_meta: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class JobSourceTrendOut(BaseModel):
    source_id: int
    days: int
    points: list[JobSnapshotOut]


class JobsAggregateTrendPoint(BaseModel):
    """Tiny per-day point for the watchlist sparkline (no recorded_at, no run_id).

    The full `JobSnapshotOut` shape is overkill for the aggregate endpoint:
    we only need (date, count) per ISIN, summed across that ISIN's sources.
    """

    snapshot_date: date
    jobs_count: int


class JobsAggregateTrendItem(BaseModel):
    isin: str
    points: list[JobsAggregateTrendPoint]


class JobsAggregateTrendsOut(BaseModel):
    days: int
    items: list[JobsAggregateTrendItem]


class JobSourceTestResult(BaseModel):
    status: str
    jobs_count: int | None = None
    error: str | None = None
    duration_ms: int
    raw_meta: dict[str, Any] | None = None


class StockJobsOut(BaseModel):
    """Aggregate view of all job sources attached to a single stock."""

    isin: str
    sources: list[JobSourceOut]
    total_latest: int | None = None
    total_delta_7d: int | None = None
    total_delta_30d: int | None = None


class StockJobsTrendOut(BaseModel):
    """Per-day summed jobs_count across all active sources of one ISIN."""

    isin: str
    days: int
    points: list[JobsAggregateTrendPoint]


class RunJobStatusOut(BaseModel):
    job_source_id: int
    source_name: str | None = None
    isin: str | None = None
    overall_status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    jobs_count: int | None = None
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)
