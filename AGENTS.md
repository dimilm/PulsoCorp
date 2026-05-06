# AGENTS.md — CompanyTracker

Tool-agnostic guide for any coding agent (Codex CLI, Claude Code, Aider,
Cursor, …) working in this repo. Cursor users additionally get the
glob-scoped rules under `.cursor/rules/*.mdc` automatically; this file is
the tool-neutral mirror.

Nested `AGENTS.md` files live in `backend/` and `frontend/` and override
this file for stack-specific work — read the closest one to whatever you
are editing.

## Project snapshot

CompanyTracker is a single-process FastAPI + React app that tracks a
watchlist of stocks, refreshes market data via `yfinance`, scrapes open
positions from career portals (Jobs pipeline) and runs manual AI agents
(Fisher, Tournament, Scenario, Red-Flag) against OpenAI / Gemini /
Ollama. Storage is SQLite. See [`README.md`](README.md) for the full
product surface and
[`docs/adr/0001-single-process-backend.md`](docs/adr/0001-single-process-backend.md)
for the scaling assumptions baked into the design.

## Repository layout

- [`backend/`](backend/) — FastAPI + SQLAlchemy 2.x + Alembic, Python
  3.12, entrypoint `app.main:app`. See [`backend/AGENTS.md`](backend/AGENTS.md).
- [`frontend/`](frontend/) — React 18 + Vite + TanStack Query + React
  Router. See [`frontend/AGENTS.md`](frontend/AGENTS.md).
- [`docker/`](docker/) — `docker-compose.yml`, per-service Dockerfiles,
  `nginx.conf`, backup helpers.
- `data/` — runtime SQLite DB + rotating backups (gitignored; on Docker
  the data lives in the `app_data` named volume instead).
- [`docs/adr/`](docs/adr/) — architecture decision records.
- [`.cursor/rules/`](.cursor/rules/) — Cursor-specific glob-scoped
  versions of these conventions.

## Ports & default login

- Backend: `http://localhost:8001` (`uvicorn app.main:app --reload --port 8001`).
- Frontend (local): `http://localhost:5173` (`npm run dev`), proxies
  `/api/*` to `8001`. Override with `VITE_BACKEND_URL`.
- Frontend (Docker): `http://localhost:8080`. The backend container is
  not exposed on the host.
- Default login on first DB bootstrap: `admin / changeme` (seeded by
  `init_db()` in [`backend/app/main.py`](backend/app/main.py)).

## Secrets

- `JWT_SECRET` (signs auth tokens) and `ENCRYPTION_KEY` (Fernet, encrypts
  the configured AI API key) are required to start the backend.
- Local: `backend/.env`. Docker: `docker/.env`. Both are gitignored —
  never commit them.
- Rotating `ENCRYPTION_KEY` invalidates the stored AI API key in
  `app_settings`; back it up before changing it in production.
- Generation snippets and PowerShell one-liner live in
  [`README.md`](README.md).

## Architecture cheatsheet

- **Refresh pipeline (per stock):**
  `resolve_symbol → fetch_quote → fetch_metrics`, tracked in `run_logs`
  + `run_stock_status`, guarded by `JobLock` against double-starts.
  Triggered manually from the watchlist or by the cron scheduler; runs
  on the in-process `RefreshWorker` thread.
- **Jobs pipeline (career-portal scrape):** separate `run_type='jobs'`
  with its own lock domain `daily_jobs_refresh`, so market and jobs
  refresh can run in parallel. Adapters live under
  [`backend/app/providers/jobs/`](backend/app/providers/jobs/); five
  HTTP adapters ship by default, three Playwright adapters require the
  optional `[playwright]` extra.
- **AI agents:** manual-only, one provider configured at a time, prompts
  under [`backend/app/agents/<id>/prompt.md`](backend/app/agents/) are
  read-only at runtime. Each run is logged in `ai_runs`.

## Cross-stack pre-commit gate

Before handing off, all three of these must be green:

```bash
(cd backend  && pytest)            && \
(cd frontend && npm run typecheck) && \
(cd frontend && npm test)
```

Stack-specific commands (uvicorn, alembic, npm scripts, conda activate)
live in the per-stack `AGENTS.md` files.

## Global do-not-touch list

- Never commit `backend/.env`, `docker/.env`, `backend/data/sqlite.db`
  or anything under `data/backups/`.
- Never edit a shipped Alembic revision under
  [`backend/migrations/versions/`](backend/migrations/versions/) — add a
  follow-up revision instead.
- Don't bypass the shared frontend API client in
  [`frontend/src/lib/`](frontend/src/lib/); it owns the CSRF header on
  mutating requests.
- AI prompts under `backend/app/agents/<id>/prompt.md` are static and
  read-only at runtime — they are not editable through the UI or API.

## Pointers

- [`README.md`](README.md) — full setup (local + Docker), backup
  restore, scaling notes, jobs adapters, AI providers.
- [`docs/adr/0001-single-process-backend.md`](docs/adr/0001-single-process-backend.md)
  — why the app is single-process, what to change before scaling out.
- [`docs/adr/0002-jobs-pipeline-integration.md`](docs/adr/0002-jobs-pipeline-integration.md)
  — jobs pipeline design and the optional Playwright extra.
- [`.cursor/rules/`](.cursor/rules/) — Cursor-only glob-scoped mirror of
  these rules (`project-overview.mdc`, `backend-python.mdc`,
  `frontend-react.mdc`, `conda.mdc`).
