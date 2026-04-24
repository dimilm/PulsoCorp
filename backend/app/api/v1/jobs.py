from fastapi import APIRouter, Depends

from app.api.deps import csrf_guard, get_current_user
from app.services.scheduler_service import start_refresh_all_background

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/refresh-all", dependencies=[Depends(csrf_guard)])
def refresh_all(_: dict = Depends(get_current_user)) -> dict:
    """Kick off a refresh on the worker thread and return immediately.

    The actual work runs on `RefreshWorker` (see `services/refresh_worker.py`)
    so the FastAPI event loop stays free. Progress can be polled via
    `GET /run-logs/current` and `GET /run-logs/{id}/stocks`.
    """
    return start_refresh_all_background()
