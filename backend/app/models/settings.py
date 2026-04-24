from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    update_hour: Mapped[int] = mapped_column(Integer, default=22, nullable=False)
    update_minute: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    update_weekends: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(32), default="openai", nullable=False)
    ai_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ai_model: Mapped[str] = mapped_column(String(128), default="gpt-4o-mini", nullable=False)
    ai_refresh_interval: Mapped[str] = mapped_column(String(16), default="monthly", nullable=False)
