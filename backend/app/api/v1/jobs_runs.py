"""Bulk-trigger endpoints for the career-portal scrape pipeline.

Lives in its own module (rather than next to ``jobs.py`` which orchestrates
the *market-data* refresh) so the URL prefix stays cleanly separated.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import csrf_guard, get_current_user
from app.services.jobs_service import (
    cancel_current_jobs_refresh,
    start_refresh_jobs_background,
)

router = APIRouter(prefix="/jobs-runs", tags=["jobs-runs"])


@router.post("/refresh-all", dependencies=[Depends(csrf_guard)])
def refresh_all_jobs(_: dict = Depends(get_current_user)) -> dict:
    """Queue a bulk job-source scrape and return immediately.

    Mirrors `/jobs/refresh-all` for the market refresh: the work runs on
    the shared `RefreshWorker` thread and progress is tracked through the
    standard `/run-logs/current` + `/run-logs/{id}/jobs` endpoints.
    """
    return start_refresh_jobs_background(manual=True)


@router.post("/refresh-all/cancel", dependencies=[Depends(csrf_guard)])
def cancel_jobs_refresh(_: dict = Depends(get_current_user)) -> dict:
    """Flag the active jobs run for cancellation; no-op if none is running."""
    return cancel_current_jobs_refresh()
