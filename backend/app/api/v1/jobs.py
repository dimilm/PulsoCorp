from fastapi import APIRouter, Depends

from app.api.deps import csrf_guard, get_current_user
from app.services.scheduler_service import (
    cancel_current_refresh,
    start_refresh_all_background,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/refresh-all", dependencies=[Depends(csrf_guard)])
def refresh_all(_: dict = Depends(get_current_user)) -> dict:
    """Kick off a refresh on the worker thread and return immediately.

    The actual work runs on `RefreshWorker` (see `services/refresh_worker.py`)
    so the FastAPI event loop stays free. Progress can be polled via
    `GET /run-logs/current` and `GET /run-logs/{id}/stocks`.

    `manual=True` bypasses the weekend skip — the user explicitly clicked the
    button, so we honour the request even on Saturday/Sunday.
    """
    return start_refresh_all_background(manual=True)


@router.post("/refresh-all/cancel", dependencies=[Depends(csrf_guard)])
def cancel_refresh_all(_: dict = Depends(get_current_user)) -> dict:
    """Request cancellation of the currently running refresh.

    Returns immediately; the worker honours the flag between stocks (and
    between retries within a stock), so the active stock may still finish
    before the run flips to `phase=finished` / `status=cancelled`.
    """
    return cancel_current_refresh()
