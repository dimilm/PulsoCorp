from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CompanyTracker"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/sqlite.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 8
    csrf_cookie_name: str = "ct_csrf"
    auth_cookie_name: str = "ct_access"
    cookie_secure: bool = True
    cookie_samesite: str = "lax"
    encryption_key: str = "change-me-32-byte-key-change-me-32b"
    daily_update_hour: int = 22
    daily_update_minute: int = 30
    skip_weekends: bool = False
    ai_refresh_interval_days: int = 30
    seed_json_path: str = "app/seed/stocks.seed.json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
