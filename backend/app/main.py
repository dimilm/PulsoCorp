from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import inspect

from app.api.v1 import ai, auth, dashboard, export_csv, import_csv, jobs, run_logs, settings, stocks, tags
from app.core.config import settings as app_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.settings import AppSettings
from app.models.stock import Stock
from app.models.user import User
from app.services.refresh_worker import worker as refresh_worker
from app.services.scheduler_service import recover_stale_locks, start_scheduler
from app.services.seed_service import load_seed_json

logger = logging.getLogger(__name__)


def _run_schema_setup() -> None:
    """Apply Alembic migrations.

    For brand-new databases we simply run `upgrade head`. For existing SQLite
    files that were originally created via `Base.metadata.create_all`, we
    detect the legacy state (tables exist, no `alembic_version` row) and stamp
    them at the 0001 baseline before running any pending upgrades. This avoids
    Alembic trying to recreate live tables on first switch-over.
    """
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    migrations_dir = backend_root / "migrations"
    if not alembic_ini.exists() or not migrations_dir.exists():
        raise RuntimeError("Alembic configuration is missing - cannot manage schema.")

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", app_settings.database_url)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    has_app_tables = "stocks" in existing_tables or "users" in existing_tables
    has_alembic = "alembic_version" in existing_tables
    if has_app_tables and not has_alembic:
        logger.info("Existing schema detected without alembic_version - stamping 0001_initial")
        command.stamp(cfg, "0001_initial")
    command.upgrade(cfg, "head")
    logger.info("Alembic migrations applied successfully.")


def init_db() -> None:
    configure_logging()
    Path("data").mkdir(parents=True, exist_ok=True)
    _run_schema_setup()
    db = SessionLocal()
    try:
        if not db.get(User, "admin"):
            db.add(User(username="admin", password_hash=hash_password("changeme"), role="admin"))
        if not db.get(AppSettings, 1):
            db.add(AppSettings(id=1))
        db.commit()

        stocks_count = db.query(Stock).count()
        if stocks_count == 0:
            imported = load_seed_json(db, app_settings.seed_json_path)
            logger.info("Seed import completed: imported=%s from %s", imported, app_settings.seed_json_path)
        else:
            logger.info("Seed import skipped: stocks already present (%s)", stocks_count)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recover_stale_locks()
    refresh_worker.start()
    start_scheduler()
    try:
        yield
    finally:
        refresh_worker.stop()


app = FastAPI(title=app_settings.app_name, lifespan=lifespan)


@app.get("/api/v1/health")
def health() -> dict:
    return {"ok": True}


app.include_router(auth.router, prefix=app_settings.api_v1_prefix)
app.include_router(stocks.router, prefix=app_settings.api_v1_prefix)
app.include_router(import_csv.router, prefix=app_settings.api_v1_prefix)
app.include_router(jobs.router, prefix=app_settings.api_v1_prefix)
app.include_router(run_logs.router, prefix=app_settings.api_v1_prefix)
app.include_router(settings.router, prefix=app_settings.api_v1_prefix)
app.include_router(ai.router, prefix=app_settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=app_settings.api_v1_prefix)
app.include_router(export_csv.router, prefix=app_settings.api_v1_prefix)
app.include_router(tags.router, prefix=app_settings.api_v1_prefix)
