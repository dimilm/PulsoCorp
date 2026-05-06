from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import csrf_guard, get_current_user, require_admin
from app.core.config import settings
from app.core.crypto import SecretCrypto
from app.db.session import get_db
from app.models.settings import AppSettings
from app.schemas.settings import SettingsOut, SettingsUpdate
from app.services.scheduler_service import sync_scheduler_from_db

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_or_create_settings(db: Session) -> AppSettings:
    row = db.get(AppSettings, 1)
    if row:
        return row
    row = AppSettings(id=1)
    db.add(row)
    db.commit()
    return row


def _to_out(row: AppSettings) -> SettingsOut:
    return SettingsOut(
        update_hour=row.update_hour,
        update_minute=row.update_minute,
        update_weekends=row.update_weekends,
        ai_provider=row.ai_provider,
        ai_endpoint=row.ai_endpoint,
        ai_model=row.ai_model,
        ai_refresh_interval=row.ai_refresh_interval,
        ai_api_key_set=bool(row.ai_api_key_encrypted),
        jobs_enabled=row.jobs_enabled,
        jobs_update_hour=row.jobs_update_hour,
        jobs_update_minute=row.jobs_update_minute,
    )


@router.get("", response_model=SettingsOut)
def get_settings(_: dict = Depends(get_current_user), db: Session = Depends(get_db)) -> SettingsOut:
    return _to_out(_get_or_create_settings(db))


@router.put("", response_model=SettingsOut, dependencies=[Depends(csrf_guard)])
def put_settings(payload: SettingsUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)) -> SettingsOut:
    row = _get_or_create_settings(db)
    data = payload.model_dump(exclude_unset=True)
    for key in [
        "update_hour",
        "update_minute",
        "update_weekends",
        "ai_provider",
        "ai_endpoint",
        "ai_model",
        "ai_refresh_interval",
        "jobs_enabled",
        "jobs_update_hour",
        "jobs_update_minute",
    ]:
        if key in data:
            setattr(row, key, data[key])
    if "ai_api_key" in data and data["ai_api_key"]:
        crypto = SecretCrypto(settings.encryption_key)
        row.ai_api_key_encrypted = crypto.encrypt(data["ai_api_key"])
    db.add(row)
    db.commit()
    db.refresh(row)
    sync_scheduler_from_db()
    return _to_out(row)
