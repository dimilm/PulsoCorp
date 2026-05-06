from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import inspect, text

from app.api.v1 import (
    ai,
    auth,
    dashboard,
    export_csv,
    import_csv,
    job_sources,
    jobs,
    jobs_runs,
    run_logs,
    settings,
    stocks,
    tags,
)
from app.core.config import settings as app_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.job_source import JobSnapshot, JobSource, RunJobStatus  # noqa: F401
from app.models.settings import AppSettings
from app.models.stock import Stock
from app.models.user import User
from app.services.refresh_worker import worker as refresh_worker
from app.services.jobs_service import recover_stale_jobs_locks
from app.services.scheduler_service import (
    recover_stale_locks,
    shutdown_scheduler,
    start_scheduler,
)
from app.services.seed_service import load_job_sources_seed_json, load_seed_json

logger = logging.getLogger(__name__)


def _run_schema_setup() -> None:
    """Apply Alembic migrations.

    For brand-new databases we simply run `upgrade head`. Two legacy states are
    handled transparently so no manual DB reset is required:

    * Tables exist but no ``alembic_version`` row (DBs originally created via
      ``Base.metadata.create_all``) -- stamp the 0001 baseline first.
    * ``alembic_version`` points at a revision that no longer exists in the
      scripts directory (DBs that ran the pre-squash 0001..0004 chain) --
      re-stamp to the current baseline. The schema is already at-or-beyond the
      squashed baseline, so this is a metadata-only fix.
    """
    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    migrations_dir = backend_root / "migrations"
    if not alembic_ini.exists() or not migrations_dir.exists():
        raise RuntimeError("Alembic configuration is missing - cannot manage schema.")

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", app_settings.database_url)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    has_app_tables = "stocks" in existing_tables or "users" in existing_tables
    has_alembic = "alembic_version" in existing_tables

    if has_alembic:
        script_dir = ScriptDirectory.from_config(cfg)
        known_revs = {rev.revision for rev in script_dir.walk_revisions()}
        with engine.connect() as conn:
            current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current and current not in known_revs:
            logger.info(
                "Stale alembic_version=%s not in scripts - re-stamping to 0001_initial",
                current,
            )
            # Raw UPDATE: command.stamp() would first try to resolve the
            # existing (now unknown) revision and abort with a CommandError,
            # so we bypass Alembic's revision walk for this metadata-only fix.
            with engine.begin() as conn:
                conn.execute(text("UPDATE alembic_version SET version_num = '0001_initial'"))
    elif has_app_tables:
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

        # Job-source seed runs whenever the table is empty. The loader is
        # idempotent (UPSERT on name+url) so re-importing after manual edits
        # only updates existing rows.
        job_sources_count = db.query(JobSource).count()
        if job_sources_count == 0:
            imported_jobs = load_job_sources_seed_json(
                db, app_settings.job_sources_seed_json_path
            )
            logger.info(
                "Job-source seed import completed: imported=%s from %s",
                imported_jobs,
                app_settings.job_sources_seed_json_path,
            )
        else:
            logger.info(
                "Job-source seed import skipped: rows already present (%s)",
                job_sources_count,
            )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recover_stale_locks()
    recover_stale_jobs_locks()
    refresh_worker.start()
    start_scheduler()
    try:
        yield
    finally:
        # Stop the cron thread first so it cannot enqueue new work after the
        # worker has been told to drain.
        shutdown_scheduler()
        refresh_worker.stop()
        # Best-effort: close the headless Chromium if any Playwright-based
        # scrape ran during this process lifetime. The import is local so
        # we do not pay for it (or fail on it) when the extra is missing.
        try:
            from app.providers.jobs import PLAYWRIGHT_AVAILABLE

            if PLAYWRIGHT_AVAILABLE:
                from app.providers.jobs.playwright_pool import PlaywrightPool

                await PlaywrightPool.shutdown()
        except Exception as exc:  # pragma: no cover - shutdown path
            logger.warning("Playwright pool shutdown failed: %s", exc)


app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
# Outermost so the request id is set before any other middleware runs and
# every emitted log line — including slowapi rejections — gets tagged.
app.add_middleware(RequestIDMiddleware)


@app.get("/api/v1/health")
def health() -> dict:
    return {"ok": True}


app.include_router(auth.router, prefix=app_settings.api_v1_prefix)
app.include_router(stocks.router, prefix=app_settings.api_v1_prefix)
app.include_router(import_csv.router, prefix=app_settings.api_v1_prefix)
app.include_router(jobs.router, prefix=app_settings.api_v1_prefix)
app.include_router(jobs_runs.router, prefix=app_settings.api_v1_prefix)
app.include_router(job_sources.router, prefix=app_settings.api_v1_prefix)
app.include_router(run_logs.router, prefix=app_settings.api_v1_prefix)
app.include_router(settings.router, prefix=app_settings.api_v1_prefix)
app.include_router(ai.router, prefix=app_settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=app_settings.api_v1_prefix)
app.include_router(export_csv.router, prefix=app_settings.api_v1_prefix)
app.include_router(tags.router, prefix=app_settings.api_v1_prefix)
