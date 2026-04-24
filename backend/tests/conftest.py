"""Shared pytest setup.

Tests run against an isolated SQLite database in a temp directory so they
never touch the production data file. Cookie security flags are relaxed for
the same reason the test client speaks plain HTTP. Both must run before
`app.main` is imported by any test module so the FastAPI app picks up the
overridden settings.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Test isolation: dedicated temp DB + relaxed cookie flags. The temp dir
# survives the test process; pytest cleans it up via the `tmp_path` fixture
# infrastructure on the next session.
_TEST_DIR = Path(tempfile.mkdtemp(prefix="companytracker-tests-"))
_TEST_DB = _TEST_DIR / "test.db"

os.environ.setdefault("COOKIE_SECURE", "false")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use")
# Use a deterministic Fernet key so encrypted values stay decryptable across
# tests within the same session.
os.environ.setdefault(
    "ENCRYPTION_KEY",
    "Zx3LrW5F0wKQnM4tGqGQwJfX7wQ2S0hJ8c8m1nP9b-c=",
)


def pytest_configure(config) -> None:  # noqa: D401 - pytest hook
    """Apply migrations and seed the admin user before any test runs.

    Modern Starlette `TestClient` only triggers the lifespan when used as a
    context manager. Our tests instantiate it directly, so we explicitly run
    `init_db()` once here.
    """
    from app.main import init_db

    init_db()
