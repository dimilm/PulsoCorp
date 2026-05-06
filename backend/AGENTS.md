# backend/AGENTS.md — FastAPI backend

Stack-specific guide for anything under `backend/`. Cross-cutting context
(layout, secrets, ports, default login, architecture cheatsheet) lives
in the [root `AGENTS.md`](../AGENTS.md) — read that first.

## Toolchain

- Python **3.12** (matches `pyproject.toml` and `docker/Dockerfile.backend`).
- Conda env name: `companytracker`. **Always run `conda activate companytracker`
  before any Python command in this folder.** This rule applies to
  `python`, `pip`, `pytest`, `alembic`, `uvicorn` — anything that needs
  the env's interpreter.
- A plain venv (`python -m venv .venv`) works too; pick one and stick to
  it for the session.

## Install

From `backend/`, with the env active:

```bash
pip install -e ".[dev]"
```

Optional Playwright extra (only needed for the `playwright_*` job
adapters under [`app/providers/jobs/`](app/providers/jobs/)):

```bash
pip install -e ".[playwright]"
python -m playwright install chromium
```

Without the extra, the JSON/HTML adapters keep working and a manual run
of a Playwright source returns a clear `pip install -e .[playwright]`
hint.

## Run

From `backend/`:

```bash
uvicorn app.main:app --reload --port 8001
```

`--reload` covers handler/service edits. **Restart manually after:**

- Changes to [`app/main.py`](app/main.py) startup or `lifespan`.
- New Alembic revisions in [`migrations/`](migrations/).

## Tests (pytest)

Always run from `backend/` so pytest picks up
[`tests/conftest.py`](tests/conftest.py); the conftest provisions an
isolated temp SQLite DB and test secrets. **Tests must never hit
`backend/data/sqlite.db`.**

```bash
pytest                          # full suite
pytest tests/test_<name>.py -x  # focused, stop on first failure
pytest -k <substring>           # filter by name
```

TDD loop: write/extend a test under `tests/test_*.py`, get it red,
implement until green, then run the whole suite before handing off.

## Schema changes

- Models live in [`app/models/`](app/models/).
- Generate a revision:

  ```bash
  alembic revision --autogenerate -m "<msg>"
  ```

- Review the generated SQL, then commit migration **and** model together.
- Never edit a migration that has shipped — add a follow-up revision.

## Style

- Use SQLAlchemy 2.x style: `db.execute(select(...))`, typed
  `Mapped[...]`.
- Keep handlers thin — push logic into [`app/services/`](app/services/)
  and [`app/providers/`](app/providers/).
- Provider integrations (OpenAI, Gemini, Ollama, yfinance) must keep
  working without a configured API key; never assume one is present.
- Don't add narrating comments (`# import foo`, `# return result`).
  Only comment non-obvious intent, trade-offs or constraints.

## Pointers

- Root [`AGENTS.md`](../AGENTS.md) — secrets, ports, architecture.
- [`README.md`](../README.md) — full backend setup including conda+VS Code
  interpreter selection and SQLite reset.
- [`docs/adr/0001-single-process-backend.md`](../docs/adr/0001-single-process-backend.md)
  — single-process scaling boundary.
- [`docs/adr/0002-jobs-pipeline-integration.md`](../docs/adr/0002-jobs-pipeline-integration.md)
  — jobs pipeline + Playwright extra.
