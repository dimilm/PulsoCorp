# CompanyTracker

FastAPI + React app that tracks a watchlist of stocks, scrapes career portals for open positions, and runs manual AI analyses per company.

- Backend: FastAPI + SQLAlchemy 2 + Alembic, SQLite, Python 3.12
- Frontend: React 18 + Vite + TanStack Query
- AI agents: Fisher, Tournament, Scenario, Red-Flag (OpenAI / Gemini / Ollama)

## Start with Docker

### 1. Create `docker/.env`

```bash
cd docker
cp .env.example .env
```

Generate secrets and paste into `docker/.env`:

```bash
# JWT_SECRET
python -c "import secrets; print(secrets.token_urlsafe(64))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

PowerShell one-liner (no Python required):

```powershell
cd docker
$jwt = [Convert]::ToBase64String((1..64 | ForEach-Object { Get-Random -Maximum 256 })) `
        -replace '\+','-' -replace '/','_' -replace '=',''
$enc = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 })) `
        -replace '\+','-' -replace '/','_'
@"
JWT_SECRET=$jwt
ENCRYPTION_KEY=$enc
"@ | Set-Content -Encoding ASCII .env
```

> Never commit `docker/.env`. Rotating `ENCRYPTION_KEY` invalidates the stored AI API key — back it up before changing it in production.

### 2. Build and run

```bash
cd docker
docker compose up --build
```

- Frontend: `http://localhost:8080`
- API docs: `http://localhost:8080/api/v1/docs`
- Default login: `admin / changeme`

> **Plain HTTP (no TLS)?** Set `COOKIE_SECURE=false` in `docker/.env` — otherwise auth cookies are silently dropped and every request fails with `{"detail":"Missing auth cookie"}`.

> **Data volume:** The SQLite DB and backups live in the `app_data` named Docker volume (not `data/`). Use `docker\restore-backups.ps1` (Windows) or `docker/restore-backups.sh` (Linux/macOS) to copy backups to the host.

> **Corporate HTTP proxy?** The compose file sets `NO_PROXY=localhost,127.0.0.1,::1` by default so healthchecks don't route through the proxy. Override in `docker/.env` if needed.

### 3. Optional: Playwright job adapters

The default image excludes Chromium. To enable `playwright_api_fetch`, `playwright_css_count`, `playwright_text_regex` adapters:

```bash
# docker/.env
INSTALL_PLAYWRIGHT=1
```

```bash
cd docker
docker compose build backend && docker compose up -d
```

> **TLS-intercepting proxy during build?** Either inject your corporate root CA into `docker/corp-ca.crt` and set `NODE_EXTRA_CA_CERTS` in the Dockerfile, or set `PLAYWRIGHT_INSECURE_DOWNLOAD=1` in `docker/.env` to skip TLS verification for the one-shot Chromium download only.

## Run locally

### Prerequisites

- Python 3.12+, Node.js 20+

### Backend

```bash
cd backend
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
cp .env.example .env   # add JWT_SECRET and ENCRYPTION_KEY
uvicorn app.main:app --reload --port 8001
```

First start creates `backend/data/sqlite.db`, runs migrations, seeds `admin / changeme` and imports `stocks.seed.json`.

**Using Conda instead of venv:**

```powershell
conda create -n companytracker python=3.12 -y
conda activate companytracker
cd backend
pip install -e ".[dev]"
Copy-Item .env.example .env   # add JWT_SECRET and ENCRYPTION_KEY
uvicorn app.main:app --reload --port 8001
```

Re-activate with `conda activate companytracker` in each new shell. See [`backend/AGENTS.md`](backend/AGENTS.md) for IDE interpreter setup.

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api/* to :8001
```

### Common chores

```bash
cd frontend && npm run typecheck          # type-check without building
cd frontend && npm run build              # production build
Remove-Item backend\data\sqlite.db        # reset local DB (PowerShell)
```

## Tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

Pre-commit gate (run from repo root):

```bash
(cd backend  && pytest)            && \
(cd frontend && npm run typecheck) && \
(cd frontend && npm test)
```

## Features

- JWT cookie + CSRF auth
- Stock watchlist with CRUD, CSV import, filters, sorting, local presets
- Market data refresh via yfinance (manual + scheduled), run logs, dashboard
- AI agents per stock: Fisher, Tournament, Scenario, Red-Flag — manual only, logged in `ai_runs`
- LLM providers: OpenAI, Gemini, Ollama (one active at a time, API key encrypted)
- Career portal scraping (Jobs pipeline) with 5 HTTP adapters + 3 optional Playwright adapters
- Daily SQLite backup rotation (14 files)
- Seed export: **Settings → Export Seed** or `GET /api/v1/export/seed-json`

## Backup & restore

Backups are written to the `app_data` volume at `/data/backups/sqlite-YYYYMMDD-HHMMSS.db` (14 rotating files).

**Copy backups to host:**

```powershell
cd docker && .\restore-backups.ps1                        # Windows
cd docker && ./restore-backups.sh                         # Linux/macOS
```

**Restore a specific backup:**

```bash
cd docker
docker compose down
docker run --rm \
  -v docker_app_data:/data \
  -v "$(pwd)/../data/backups:/host:ro" \
  alpine:3.20 sh -c 'cp /host/sqlite-YYYYMMDD-HHMMSS.db /data/sqlite.db'
docker compose up --build
```

**Reset to fresh DB** (drops all data):

```bash
cd docker && docker compose down -v && docker compose up --build
```

## Architecture & scaling

CompanyTracker is a **single-process** app by design. The refresh pipeline runs on a `RefreshWorker` thread inside the FastAPI process; concurrency is guarded by a DB-level `JobLock`. This works correctly for one instance but breaks under horizontal scaling (in-memory cancel registry, in-memory rate limiter, multiple cron instances).

See [`docs/adr/0001-single-process-backend.md`](docs/adr/0001-single-process-backend.md) for the full trade-off analysis and what to change before scaling out.

## Further reading

- [`AGENTS.md`](AGENTS.md) — tool-neutral coding guide (architecture cheatsheet, do-not-touch list)
- [`backend/AGENTS.md`](backend/AGENTS.md) — backend-specific conventions
- [`frontend/AGENTS.md`](frontend/AGENTS.md) — frontend-specific conventions
- [`docs/adr/0001-single-process-backend.md`](docs/adr/0001-single-process-backend.md) — single-process design rationale
- [`docs/adr/0002-jobs-pipeline-integration.md`](docs/adr/0002-jobs-pipeline-integration.md) — jobs pipeline and Playwright extra
