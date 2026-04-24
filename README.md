# CompanyTracker

MVP implementation of the CompanyTracker plan with FastAPI + React.

## Start with Docker

### 1. Create `docker/.env` with required secrets

`docker-compose.yml` requires two secrets: `JWT_SECRET` (signs auth tokens) and
`ENCRYPTION_KEY` (Fernet key that encrypts the OpenAI API key in the DB). Without
them you'll see:

```
error while interpolating services.backend.environment.JWT_SECRET:
required variable JWT_SECRET is missing a value: JWT_SECRET must be set in .env
```

Copy the template and generate fresh values:

```bash
cd docker
cp .env.example .env
```

Generate the values (Python required) and paste them into `docker/.env`:

```bash
# JWT_SECRET: 64-byte URL-safe random token
python -c "import secrets; print(secrets.token_urlsafe(64))"

# ENCRYPTION_KEY: valid 32-byte URL-safe base64 Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

PowerShell one-liner (Windows, no Python required) that writes both values
straight into `docker/.env`:

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

> Never commit `docker/.env`. Rotating `ENCRYPTION_KEY` invalidates any stored
> OpenAI API key, so back it up before changing it in production.

### 2. Build and run

```bash
cd docker
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend docs (direct): `http://localhost:8001/api/v1/docs`
- Backend docs (via frontend proxy): `http://localhost:8080/api/v1/docs`
- Default login: `admin / changeme`

## Run locally without Docker

Useful for fast iteration with hot reload, breakpoints in the IDE, and direct
access to the SQLite file.

### Prerequisites

- Python **3.12+** (matches `backend/pyproject.toml` and `Dockerfile.backend`)
- Node.js **20+** with npm
- A C toolchain only if `cryptography` / `argon2` need to compile from source
  (Windows usually gets prebuilt wheels)

### Backend (FastAPI on port 8001)

```bash
cd backend

# 1. Virtualenv
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

# 2. Install runtime + dev dependencies (editable so code edits are picked up)
pip install -e ".[dev]"

# 3. Local secrets
cp .env.example .env
# then put real values into backend/.env, e.g. on Linux/macOS:
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))"     >> .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env

# 4. Run the API with auto-reload on port 8001 (matches the Vite proxy default)
uvicorn app.main:app --reload --port 8001
```

On first start the backend creates `backend/data/sqlite.db`, applies Alembic
migrations, seeds the `admin / changeme` user and imports `stocks.seed.json`.

### Frontend (Vite dev server on port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api/*` to
`http://localhost:8001` (see `frontend/vite.config.ts`); override with
`VITE_BACKEND_URL` if your backend runs elsewhere.

### Common chores

```bash
# Type-check the React app without producing a build
cd frontend && npm run typecheck

# Production build (also runs tsc --noEmit first)
cd frontend && npm run build

# Reset the local DB so the seed import runs again
rm backend/data/sqlite.db          # PowerShell: Remove-Item backend\data\sqlite.db
```

## Tests

### Backend (pytest)

`backend/tests/conftest.py` provisions an isolated temp SQLite DB and sets test
secrets, so the suite never touches `backend/data/sqlite.db`. Run from the
`backend/` folder with the virtualenv active:

```bash
cd backend
pytest                          # all suites
pytest -k crypto                # filter by name
pytest tests/test_health.py -v  # single file, verbose
pytest --maxfail=1 -x           # stop on first failure
```

If you skipped the dev extras above, install just pytest with
`pip install pytest`.

### Frontend (Vitest + Testing Library)

```bash
cd frontend
npm test               # one-shot run (CI mode)
npm run test:watch     # interactive watch mode
npx vitest run src/lib/colorRules.test.ts   # single file
```

### Recommended pre-commit gate

```bash
# from repo root
(cd backend  && pytest)            && \
(cd frontend && npm run typecheck) && \
(cd frontend && npm test)
```

## Development flow with Cursor

A workflow that plays well with this codebase:

1. **Pick the slice.** Open `Anforderungen.md` and `plan-umsetzung.md` and
   identify the smallest user-visible change (one endpoint + one screen, or one
   pipeline step). Keep PRs scoped to that slice.
2. **Open both stacks in long-running terminals** so Cursor can read their
   output instead of restarting them per turn:
   - Terminal A: `cd backend && uvicorn app.main:app --reload --port 8001`
   - Terminal B: `cd frontend && npm run dev`
   - Terminal C: `cd frontend && npm run test:watch` (optional, for TDD on the
     UI)
3. **Plan in Plan Mode for non-trivial changes.** Use Cursor's Plan mode for
   anything touching the refresh pipeline, the AI providers, or auth — these
   span backend + frontend + scheduler and benefit from a written plan before
   editing.
4. **Reference files with `@`.** Drop the agent into the right context, e.g.
   `@backend/app/services/refresh_worker.py @frontend/src/pages/Watchlist.tsx`,
   instead of describing them in prose. Same for canvases and docs:
   `@canvases/refresh-flow.canvas.tsx`, `@Anforderungen.md`.
5. **TDD-style loop for the backend.**
   - Add or update a test under `backend/tests/test_*.py` first.
   - Run the focused test: `pytest tests/test_<name>.py -x`.
   - Implement until green, then run the whole suite: `pytest`.
   - Ask the agent to update the corresponding API client in
     `frontend/src/lib/` and the screen that consumes it.
6. **TDD-style loop for the frontend.**
   - With `npm run test:watch` running, add a Vitest case in
     `frontend/src/**/*.test.ts(x)`.
   - Implement the hook/component until the watcher turns green.
   - Run `npm run typecheck` before committing — `vite build` also runs `tsc
     --noEmit` so type errors block the production build.
7. **Verify end-to-end manually.** Log in at `http://localhost:5173` with
   `admin / changeme`, trigger the affected flow (e.g. *Watchlist → Alle
   aktualisieren*), and inspect `/runs` for `run_logs` / `run_stock_status`
   updates. The backend's auto-reload will already be on the new code.
8. **Pre-commit gate.** Run the three commands from the *Tests* section above.
   Only commit after all three are green.
9. **Restart only when needed.** Schema changes (new Alembic revision) and
   changes to `app/main.py` startup logic require restarting the uvicorn
   process; pure handler/service edits are picked up by `--reload`.
10. **Keep secrets local.** `.env`, `docker/.env` and `backend/.env` are in
    `.gitignore`. If you rotate `ENCRYPTION_KEY`, the stored OpenAI API key in
    `app_settings` becomes unreadable and must be re-entered in the UI.

## Included MVP blocks

- Auth with JWT cookie + CSRF header
- Stock CRUD
- CSV import (`Comp_List.csv`)
- Manual and scheduled refresh with yfinance
- Advanced watchlist filters, sorting and local presets
- Run logs
- Extended dashboard (winners/losers, run status, day delta)
- AI evaluation with OpenAI/Ollama endpoints plus fallback heuristics
- Encrypted API key storage in settings
- Daily SQLite backup rotation (14 files)

## Aktualisierungs-Flow

Wenn der Nutzer auf **„Alle aktualisieren"** klickt (oder der Cron läuft), läuft jede Aktie
durch dieselbe vierstufige Pipeline. Ein detailliertes Bild gibt es zusätzlich als Canvas
unter `canvases/refresh-flow.canvas.tsx` (in Cursor öffnen).

```mermaid
flowchart LR
    subgraph Trigger
        UIAll["Watchlist · Alle aktualisieren"]
        UIOne["Watchlist · einzelne Aktie"]
        Cron["APScheduler · cron"]
    end

    UIAll -->|POST /jobs/refresh-all| Bg["start_refresh_all_background"]
    Cron --> Bg
    UIOne -->|POST /stocks/{isin}/refresh| Pipe

    Bg -->|RefreshWorker.submit| Pipe

    subgraph Pipe["Pipeline pro Aktie"]
        S1["1 Symbol<br/>resolve_symbol"] --> S2["2 Kurs<br/>fetch_quote"]
        S2 --> S3["3 Kennzahlen<br/>fetch_metrics"]
        S3 --> S4["4 KI<br/>evaluate_stock"]
    end

    S1 -. yfinance.Search .-> Yf[(Yahoo Finance)]
    S2 -. yf.Ticker.info .-> Yf
    S3 -. yf.Ticker.info + history .-> Yf
    S4 -. HTTPS .-> Ai[(OpenAI / Ollama / Fallback)]

    S1 --> RS["run_stock_status<br/>(per-Schritt commit)"]
    S2 --> RS
    S3 --> RS
    S4 --> RS

    Pipe --> RL["run_logs<br/>(phase, counter, status)"]
```

### Was wird pro Lauf geschrieben

| Schritt     | Externe Quelle                            | DB-Tabelle                  | Retry                  |
|-------------|-------------------------------------------|-----------------------------|------------------------|
| Symbol      | `yfinance.Search` · Yahoo-Link-Parser     | `stocks.ticker_override`    | kein Retry             |
| Kurs        | Yahoo Finance via `yfinance`              | `market_data` (price, day_change, status, currency) | bis zu 4x mit 0/2/4/8s Backoff |
| Kennzahlen  | Yahoo Finance via `yfinance` (info + 5y history) | `metrics` (PE, Dividende, Markt­kap, Equity/Debt, Revenue Growth, …) | bis zu 4x mit 0/2/4/8s Backoff |
| KI          | OpenAI · Ollama · Heuristik-Fallback      | `valuations` (Scores, Fair Values, Empfehlung) | kein Retry · Skip wenn `last_ai_at` jünger als `ai_refresh_interval` |
| Tracking    | —                                         | `run_logs` + `run_stock_status` | — |

> Hinweis: `pe_min/avg/max_5y` werden aus den Monats-Schlusskursen der letzten 5 Jahre
> geteilt durch die jeweils gueltige Quartals- bzw. Jahres-EPS rekonstruiert. Liefert
> Yahoo Finance keine EPS-Historie, faellt der Provider auf das aktuelle `trailingEps`
> zurueck (rein kursgetriebene Spannweite); fehlt auch das, bleiben die Felder leer
> (`null`) statt einen irrefuehrenden Naeherungswert anzuzeigen.

Ein laufender Job ist über `JobLock` gegen Doppelstarts geschützt; ein zweiter Klick gibt
nur die `run_id` des laufenden Jobs zurück. Der Live-Status pro Unternehmen (Symbol → Kurs →
Kennzahlen → KI mit Zeitstempeln und Fehlertexten) ist während des Laufs unter `/runs`
sichtbar; die Detailzeilen werden für die zwei jüngsten Läufe behalten.

## Auto-Seed on first startup

- The initial stock universe is generated from `Comp_List.csv` into `backend/app/seed/stocks.seed.json`.
- On backend startup, this seed is imported automatically **only when the `stocks` table is empty**.
- If stocks already exist, seed import is skipped.
- Default seed path: `app/seed/stocks.seed.json` (configurable via `SEED_JSON_PATH`).

To run initial import again:

- delete/reset `data/sqlite.db`, then restart containers, or
- point `SEED_JSON_PATH` to a different seed file and start with an empty DB.

## Backup Restore

1. Stop stack:
   - `cd docker`
   - `docker compose down`
2. Pick backup from `data/backups/` (e.g. `sqlite-YYYYMMDD-HHMMSS.db`)
3. Copy backup file to `data/sqlite.db`
4. Start stack again:
   - `docker compose up --build`
5. Verify API and UI:
   - `http://localhost:8001/api/v1/health`
   - login in frontend and check `/runs` plus `/watchlist`
