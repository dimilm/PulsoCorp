from pydantic import BaseModel


class SettingsOut(BaseModel):
    update_hour: int
    update_minute: int
    update_weekends: bool
    ai_provider: str
    ai_endpoint: str | None
    ai_model: str
    ai_refresh_interval: str


class SettingsUpdate(BaseModel):
    update_hour: int | None = None
    update_minute: int | None = None
    update_weekends: bool | None = None
    ai_provider: str | None = None
    ai_endpoint: str | None = None
    ai_model: str | None = None
    ai_refresh_interval: str | None = None
    ai_api_key: str | None = None
