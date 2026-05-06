# CompanyTracker

MVP implementation of the CompanyTracker plan with FastAPI + React.

## Start with Docker

### 1. Create `docker/.env` with required secrets

`docker-compose.yml` requires two secrets: `JWT_SECRET` (signs auth tokens) and
`ENCRYPTION_KEY` (Fernet key that encrypts the configured AI API key — OpenAI,
Gemini, etc. — in the DB). Without
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
> AI API key (OpenAI, Gemini, …), so back it up before changing it in production.

### 2. Build and run

```bash
cd docker
docker compose up --build
```

- Frontend: `http://localhost:8080`
- Backend docs (direct): `http://localhost:8001/api/v1/docs`
- Backend docs (via frontend proxy): `http://localhost:8080/api/v1/docs`
- Default login: `admin / changeme`

> **Deploying over plain HTTP (no TLS in front)?** The auth + CSRF cookies are
> issued with the `Secure` flag by default, so browsers silently drop them on a
> non-HTTPS connection — login appears to succeed but every follow-up request
> fails with `{"detail":"Missing auth cookie"}`. Set `COOKIE_SECURE=false` in
> `docker/.env` (see `.env.example`) before `docker compose up` and switch it
> back to `true` once HTTPS is in front of the deployment.

> The SQLite database and the rotating backups live in the **`app_data` named
> Docker volume**, not in the host `data/` folder. We don't bind-mount `data/`
> on Docker Desktop / Windows because the gRPC-FUSE layer surfaces sub-paths
> as `nobody:nobody` mode 0755 and rejects writes from inside the container,
> which crashes Alembic on startup and the daily backup job. The named volume
> lives on ext4 inside WSL2 (Windows) or directly on the Docker engine's
> filesystem (Linux/macOS), so permissions and SQLite locking behave normally
> on every platform. Use `docker\restore-backups.ps1` (Windows) or
> `docker/restore-backups.sh` (Linux/macOS) to copy the rotating backup files
> out to the host whenever you need them — see *Backup Restore* below.

> **Behind a corporate HTTP proxy?** Some Docker Desktop installs (especially
> at companies with Zscaler / Netskope / similar) inject `HTTP_PROXY` and
> `HTTPS_PROXY` into every container. Without an explicit `NO_PROXY`, both
> healthchecks below route their loopback request (`http://localhost:8000/...`
> for the backend, `http://localhost/healthz` for nginx) through that proxy
> and fail with a `502 Could not resolve or connect to proxy or host` — even
> though the app itself answers fine. The compose file exempts loopback by
> default (`NO_PROXY=localhost,127.0.0.1,::1`); override via `NO_PROXY=...`
> in `docker/.env` only if you need to widen the no-proxy list further (e.g.
> for an internal package mirror).

### 3. Optional: enable Playwright job adapters in Docker

The default Docker image **does not** include Chromium so it stays slim
(~500 MB savings, see [ADR 0002](docs/adr/0002-jobs-pipeline-integration.md)).
If you have a `job_source` whose `adapter_type` is one of
`playwright_api_fetch`, `playwright_css_count` or `playwright_text_regex`,
the backend will refuse to refresh that source with:

```
adapter_type 'playwright_text_regex' requires the Playwright extra.
Install it with `pip install -e .[playwright]` and run
`python -m playwright install chromium` once.
```

To enable the Playwright adapters in Docker, set the build-time toggle in
`docker/.env` and rebuild:

```bash
# docker/.env
INSTALL_PLAYWRIGHT=1
```

```bash
cd docker
docker compose build backend
docker compose up -d
```

The backend image now installs `pip install .[playwright]` and bakes
Chromium plus its system libraries (`libnss3`, `libatk1.0-0`, …) into the
image via `playwright install --with-deps chromium`. The browser cache is
pinned to `/opt/playwright` (via `PLAYWRIGHT_BROWSERS_PATH`) so the
unprivileged `app` user can read it after `gosu` drops privileges. Switching
back to the slim image is a one-line change (`INSTALL_PLAYWRIGHT=0`) plus
another `docker compose up --build`.

**Behind a TLS-intercepting corporate proxy?** `playwright install`
internally calls a Node-based downloader that ignores the system trust
store and validates against its own bundled CA list, so the build aborts
with:

```
Downloading Chrome for Testing ... from https://cdn.playwright.dev/...
Error: unable to get local issuer certificate
code: 'UNABLE_TO_GET_ISSUER_CERT_LOCALLY'
```

Two ways out, in order of preference:

1. **Inject the corporate root CA (clean, recommended).** Drop your root CA
   in PEM format into `docker/corp-ca.crt`, then add this once to
   `docker/Dockerfile.backend` right before the `playwright install` line:
   ```dockerfile
   COPY docker/corp-ca.crt /usr/local/share/ca-certificates/corp-ca.crt
   ENV NODE_EXTRA_CA_CERTS=/usr/local/share/ca-certificates/corp-ca.crt
   ```
   Leave `PLAYWRIGHT_INSECURE_DOWNLOAD=0`. TLS verification stays on.
2. **Skip TLS verification for the one-shot download (quick).** Set in
   `docker/.env`:
   ```
   PLAYWRIGHT_INSECURE_DOWNLOAD=1
   ```
   The build then exports `NODE_TLS_REJECT_UNAUTHORIZED=0` only for the
   single `playwright install` invocation. Chromium is then in the image
   and runtime Playwright never contacts the CDN again, so the runtime app
   keeps verifying TLS normally. Acceptable as a workaround when your
   corporate proxy already MITMs all egress traffic anyway, but flag #1
   is the principled fix.

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

### Backend with Conda (alternative to venv)

If your local Python comes from Anaconda / Miniconda only, use conda just to
provide an isolated Python 3.12 and let pip read `pyproject.toml` exactly like
the venv path above and `docker/Dockerfile.backend` do. That keeps
`backend/pyproject.toml` the single source of truth for versions.

```powershell
# 1. One-time: create the env (Python 3.12 to match pyproject.toml)
conda create -n companytracker python=3.12 -y
conda activate companytracker

# 2. Install runtime + dev deps (editable). Run from backend/.
cd backend
pip install -e ".[dev]"

# 3. Local secrets (writes into backend/.env)
Copy-Item .env.example .env
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))" `
    | Add-Content .env
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" `
    | Add-Content .env

# 4. Run the API on port 8001 (matches the Vite proxy default)
uvicorn app.main:app --reload --port 8001
```

Re-activate the env in every new shell with `conda activate companytracker`.
`pytest` and `alembic` land in the same env, so the *Tests* and *Schema
changes* sections work unchanged — just make sure the env is active.

Point Cursor / VS Code at the same interpreter so Pylance, the run button and
the integrated terminal all use the conda env:

1. **Install the Python extension** (once per machine).
   `Ctrl+Shift+X` → search *Python* → install the Microsoft extension named
   *Python* (publisher: Microsoft). Restart the editor afterwards.
2. **Find the env's interpreter path.** From a shell where
   `conda activate companytracker` is active, run:

   ```powershell
   python -c "import sys; print(sys.executable)"
   ```

   Typical Windows output: `C:\Users\<you>\anaconda3\envs\companytracker\python.exe`.
3. **Select the interpreter.** `Ctrl+Shift+P` → *Python: Select Interpreter*
   → Enter. Pick `Python 3.12.x ('companytracker': conda)` from the list. If
   it is missing, choose *Enter interpreter path…* and paste the path from
   step 2.
4. **Verify.** The status bar bottom-right should show
   `Python 3.12.x ('companytracker')`, new integrated terminals should open
   with the `(companytracker)` prefix, and `from fastapi import FastAPI`
   resolves without red squiggles.

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
    `.gitignore`. If you rotate `ENCRYPTION_KEY`, the stored AI API key
    (OpenAI / Gemini / …) in `app_settings` becomes unreadable and must be
    re-entered in the UI.

## Included MVP blocks

- Auth with JWT cookie + CSRF header
- Stock CRUD
- CSV import (`Comp_List.csv`)
- Manual and scheduled refresh with yfinance
- Advanced watchlist filters, sorting and local presets
- Run logs
- Extended dashboard (winners/losers, run status, day delta)
- Modular AI agents (Fisher / Tournament / Scenario / Red-Flag) with OpenAI /
  Google Gemini / Ollama as interchangeable LLM providers
- Encrypted API key storage in settings
- Daily SQLite backup rotation (14 files)
- Karriereportal-Scrape (offene Stellen pro Unternehmen, eigener Cron mit
  paralleler Lock-Domäne, Trend-Charts auf der Stock-Detail-Seite und eine
  dedizierte `/jobs`-Seite zur Quellen-Verwaltung)

### KI-Analysen (Agenten)

Die KI-Bewertung ist **rein manuell pro Unternehmen** und wird **nicht** mehr
während des Refresh-Laufs ausgeführt. Auf der Detailseite einer Aktie steht
ein eigener Bereich *KI-Analysen*, der pro Agent eine Karte zeigt: aktueller
Run, „Ausführen"-Button, Prompt-Modal (read-only) und Verlauf der letzten
Läufe. Jeder Lauf wird in `ai_runs` mit Input, Output, Provider, Modell,
Kostenabschätzung und Dauer protokolliert.

| Agent        | ID            | Output                                                              |
|--------------|---------------|---------------------------------------------------------------------|
| Fisher       | `fisher`      | 15-Punkte-Checkliste mit Rating (0/1/2), Gesamtscore, Verdict       |
| Tournament   | `tournament`  | Bracket-Turnier gegen Peer-Aktien über 7 Vergleichskategorien       |
| Scenario     | `scenario`    | Bull/Base/Bear-Szenarien mit Wahrscheinlichkeiten und Erwartungswert |
| Red-Flag     | `redflag`     | Risiko-Scan mit Severity-Liste und Gesamtrisiko                     |

Der Tournament-Agent nimmt optional eine eigene Peer-Liste entgegen (sonst
schlägt das Backend automatisch ähnliche Sektor-Aktien vor). Die Prompts liegen
statisch unter `backend/app/agents/<agent>/prompt.md` und sind über die UI nur
lesbar — sie können nicht zur Laufzeit verändert werden.

REST:

- `GET /api/v1/ai/agents` — Liste aller registrierten Agenten inkl. JSON-Schema
- `GET /api/v1/ai/agents/{id}/prompt` — Roher Prompt-Text (text/plain)
- `POST /api/v1/ai/agents/{id}/run/{isin}` — Agent für eine Aktie ausführen
- `GET /api/v1/ai/agents/{id}/runs/{isin}` — Letzte Läufe für Agent + Aktie
- `GET /api/v1/ai/runs/{run_id}` — Ein konkreter Lauf im Detail

### AI provider configuration

Der LLM-Provider wird in den Einstellungen gewählt; alle Agenten nutzen den
gleichen Provider. Defaults wenn `ai_endpoint` leer bleibt:

| Provider | Default endpoint                                            | Key source                                                  |
|----------|-------------------------------------------------------------|-------------------------------------------------------------|
| OpenAI   | `https://api.openai.com/v1/chat/completions`                | platform.openai.com → API keys                              |
| Gemini   | `https://generativelanguage.googleapis.com/v1beta`          | [Google AI Studio](https://aistudio.google.com/app/apikey)  |
| Ollama   | `http://localhost:11434/api/generate`                       | none (local)                                                |

Switching providers requires re-entering the API key (only one is stored at a
time, encrypted with `ENCRYPTION_KEY`).

## Aktualisierungs-Flow

Wenn der Nutzer auf **„Alle aktualisieren"** klickt (oder der Cron läuft), läuft jede Aktie
durch dieselbe dreistufige Pipeline. KI-Analysen sind **nicht** Teil dieser Pipeline und
werden ausschließlich manuell pro Aktie aus dem Detail-Screen gestartet. Ein detailliertes
Bild gibt es zusätzlich als Canvas unter `canvases/refresh-flow.canvas.tsx` (in Cursor öffnen).

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
    end

    S1 -. yfinance.Search .-> Yf[(Yahoo Finance)]
    S2 -. yf.Ticker.info .-> Yf
    S3 -. yf.Ticker.info + history .-> Yf

    S1 --> RS["run_stock_status<br/>(per-Schritt commit)"]
    S2 --> RS
    S3 --> RS

    Pipe --> RL["run_logs<br/>(phase, counter, status)"]

    subgraph ManuellAI["Manuell pro Aktie · Detail-Seite"]
        AIBtn["KI-Agent · Ausführen"] --> AIRun["POST /ai/agents/{id}/run/{isin}"]
        AIRun --> AIRes["ai_runs<br/>(input/output/cost)"]
        AIRun -. HTTPS .-> Ai[(OpenAI / Gemini / Ollama)]
    end
```

### Was wird pro Lauf geschrieben

| Schritt     | Externe Quelle                            | DB-Tabelle                  | Retry                  |
|-------------|-------------------------------------------|-----------------------------|------------------------|
| Symbol      | `yfinance.Search` · Yahoo-Link-Parser     | `stocks.ticker_override`    | kein Retry             |
| Kurs        | Yahoo Finance via `yfinance`              | `market_data` (price, day_change, status, currency) | bis zu 4x mit 0/2/4/8s Backoff |
| Kennzahlen  | Yahoo Finance via `yfinance` (info + 5y history) | `metrics` (PE, Dividende, Markt­kap, Equity/Debt, Revenue Growth, …) | bis zu 4x mit 0/2/4/8s Backoff |
| Tracking    | —                                         | `run_logs` + `run_stock_status` | — |

KI-Läufe werden **separat** und nur auf Anforderung in `ai_runs` geschrieben
(eine Zeile pro Agent-Ausführung mit Input-, Result-Payload, Provider, Modell,
Kostenabschätzung und Dauer). Sie haben keine eigene Phase im `run_logs`-Modell.

> Hinweis: `pe_min/avg/max_5y` werden aus den Monats-Schlusskursen der letzten 5 Jahre
> geteilt durch die jeweils gueltige Quartals- bzw. Jahres-EPS rekonstruiert. Liefert
> Yahoo Finance keine EPS-Historie, faellt der Provider auf das aktuelle `trailingEps`
> zurueck (rein kursgetriebene Spannweite); fehlt auch das, bleiben die Felder leer
> (`null`) statt einen irrefuehrenden Naeherungswert anzuzeigen.

Ein laufender Job ist über `JobLock` gegen Doppelstarts geschützt; ein zweiter Klick gibt
nur die `run_id` des laufenden Jobs zurück. Der Live-Status pro Unternehmen (Symbol → Kurs →
Kennzahlen mit Zeitstempeln und Fehlertexten) ist während des Laufs unter `/runs` sichtbar;
die Detailzeilen werden für die zwei jüngsten Läufe behalten.

## Auto-Seed on first startup

- The initial stock universe is generated from `Comp_List.csv` into `backend/app/seed/stocks.seed.json`.
- On backend startup, this seed is imported automatically **only when the `stocks` table is empty**.
- If stocks already exist, seed import is skipped.
- Default seed path: `app/seed/stocks.seed.json` (configurable via `SEED_JSON_PATH`).

To run initial import again:

- delete/reset `data/sqlite.db`, then restart containers, or
- point `SEED_JSON_PATH` to a different seed file and start with an empty DB.

### Aktuellen DB-Stand als Seed exportieren

Statt `stocks.seed.json` manuell zu pflegen, kann der aktuelle DB-Stand
(inkl. `tags`, `tranches`, `reasoning` und Links) als neuer
Seed exportiert werden:

- Im Frontend unter **Einstellungen → Seed exportieren** klicken (lädt
  `stocks.seed.json` herunter).
- Alternativ direkt per API:
  `GET /api/v1/export/seed-json` (Auth erforderlich).
- Heruntergeladene Datei nach `backend/app/seed/stocks.seed.json` kopieren
  und committen — beim nächsten leeren Bootstrap (`stocks` ist leer) wird
  der neue Stand automatisch geladen, inkl. Tags.

## Backup Restore

The `backup` service writes a rotating snapshot of the SQLite DB to
`/data/backups/sqlite-YYYYMMDD-HHMMSS.db` inside the `app_data` named volume
(keeping the 14 most recent files). To inspect or restore one:

### 1. Copy backups to the host

Both scripts use `docker cp` from the running backend container when it's up,
and fall back to mounting the `docker_app_data` volume into a temporary alpine
container when the stack is down. Default destination is `<repo>/data/backups/`.

**Windows (PowerShell)**

```powershell
cd docker
.\restore-backups.ps1
.\restore-backups.ps1 -Destination 'D:\snapshots'   # custom destination
```

**Linux / macOS (bash)**

```bash
cd docker
chmod +x restore-backups.sh    # first time only
./restore-backups.sh
./restore-backups.sh /tmp/snapshots                 # custom destination
```

### 2. Restore a backup into the live volume

**Windows (PowerShell)**

```powershell
cd docker
docker compose down
docker run --rm `
  -v docker_app_data:/data `
  -v "${PWD}\..\data\backups:/host:ro" `
  alpine:3.20 sh -c 'cp /host/sqlite-YYYYMMDD-HHMMSS.db /data/sqlite.db'
docker compose up --build
```

**Linux / macOS (bash)**

```bash
cd docker
docker compose down
docker run --rm \
  -v docker_app_data:/data \
  -v "$(pwd)/../data/backups:/host:ro" \
  alpine:3.20 sh -c 'cp /host/sqlite-YYYYMMDD-HHMMSS.db /data/sqlite.db'
docker compose up --build
```

### 3. Verify

- `http://localhost:8001/api/v1/health` returns `{"ok": true}`
- Log in at `http://localhost:8080` and confirm `/runs` and `/watchlist` show
  the expected data.

### Reset to a fresh DB

If you want the seed import to run again from scratch:

```bash
cd docker
docker compose down -v   # -v also drops the app_data volume (irreversible!)
docker compose up --build
```

## Deployment & scaling assumptions

CompanyTracker is intentionally a **single-process** application. Several
design choices only hold under that assumption — please re-evaluate them
before scaling horizontally.

### Single-process design

* The refresh pipeline runs on a dedicated thread (`RefreshWorker`) inside
  the same Python process as the FastAPI app. The cron job
  (`cron_scheduler`) and the manual entrypoints share that worker.
* Job concurrency is enforced by an atomic DB row (`JobLock` in
  `lock_manager.py`). It is correct across processes, but the in-memory
  cancellation registry (`refresh_lock._cancelled_run_ids`) is **not**:
  flagging a run for cancel only takes effect on the worker that owns
  the run. With multiple backend instances a cancel could miss its target.
* The slowapi rate-limiter (`/auth/login`, `5/minute`) defaults to an
  in-memory store, so each backend instance enforces the limit
  independently. Behind a load balancer that round-robins requests this
  effectively raises the limit by `N`.
* The cron scheduler (`apscheduler.BackgroundScheduler`) is started in
  every process. With more than one instance you'd run the daily refresh
  multiple times — the lock prevents data corruption, but you'd waste
  market-data API budget.

### Storage

* SQLite is the only supported backend today (`database_url` in
  `app/core/config.py`). Migrations and SQL idioms are kept ANSI where
  possible — the only deliberate sqlite-specific call is the
  `INSERT … ON CONFLICT DO NOTHING` for the lock row in `lock_manager.py`.
* SQLite tolerates exactly one writer at a time. The single-process
  assumption above is what keeps the write contention manageable.

### When you need to scale out

Migrating to multiple instances or a managed Postgres is feasible but
will require, at minimum:

* Replacing the in-memory cancel registry with a DB-backed flag (or a
  dedicated message bus).
* Switching the rate-limit storage to Redis (`slowapi` supports it
  out of the box) so the per-IP limit is global.
* Running the cron job in exactly one place (e.g. a `--scheduler-only`
  process or an external cron) instead of every replica.
* Auditing the `lock_manager.py` `INSERT … ON CONFLICT` for the target
  database (Postgres has equivalent syntax, MySQL needs a translation).

ADR `docs/adr/0001-single-process-backend.md` captures this trade-off in
more detail.

## Karriereportal-Scrape (Jobs)

CompanyTracker scrapt täglich (Default 02:00 lokale Zeit) die in
`job_sources` hinterlegten Karriereportale und speichert die Anzahl
offener Stellen als `JobSnapshot` ab. Die Pipeline teilt sich Worker und
Run-Tabelle mit dem Marktdaten-Refresh, läuft aber unter einem eigenen
`run_type='jobs'` und einer eigenen Lock-Domäne (`daily_jobs_refresh`),
sodass Markt- und Job-Lauf parallel laufen können.

### Unterstützte Adapter

Fünf Adapter laufen rein auf `httpx` und sind im Standard-Backend immer
verfügbar:

| Adapter                | Idee                                                                  |
|------------------------|------------------------------------------------------------------------|
| `static_html`          | GET HTML, BeautifulSoup-Selector zählt passende Elemente.              |
| `json_get_path_int`    | GET JSON, integer am dotted path (`meta.totalHits`).                   |
| `json_get_array_count` | GET JSON, Länge eines Arrays (`jobs` → `len(...)`).                    |
| `json_post_path_int`   | POST JSON-Payload, integer am dotted path.                             |
| `json_post_facet_sum`  | POST JSON-Payload, Counts in `facets.map.<facet_field>` summieren.     |

Drei Adapter brauchen einen echten Browser und liegen hinter dem
optionalen Extra `backend[playwright]`:

| Adapter                  | Idee                                                                          |
|--------------------------|--------------------------------------------------------------------------------|
| `playwright_api_fetch`   | Portal in Chromium öffnen (Cookies/Cloudflare), API per `fetch()` aufrufen.    |
| `playwright_css_count`   | Portal rendern, DOM-Elemente per CSS-Selector zählen.                          |
| `playwright_text_regex`  | Portal rendern, Counter per Regex aus dem sichtbaren Text extrahieren.         |

Aktivieren mit:

```powershell
cd backend
pip install -e .[playwright]
python -m playwright install chromium
```

Ohne Extra wird der Adapter sauber abgewiesen: das Backend startet
weiterhin, die JSON-/HTML-Adapter scrapen normal weiter, und ein
manueller Test einer Playwright-Quelle liefert eine klare
`pip install -e .[playwright]`-Hinweismeldung. Details siehe
[ADR 0002](docs/adr/0002-jobs-pipeline-integration.md).

### Quellen verwalten

Im Frontend unter **Jobs** (Navigation oben) lassen sich Quellen
anlegen, bearbeiten und einzeln scrapen. Auf der Detailseite einer
Aktie zeigt der Abschnitt **Offene Stellen** die aggregierten Counts
plus 7-/30-Tage-Delta und einen Mini-Trend pro verknüpfter Quelle.

### Importer für die Legacy-Daten aus `11_JobCounter`

Der ursprüngliche Stand-alone-Scraper liegt nicht mehr im Repo. Falls
noch ein Daten-Snapshot vorhanden ist:

```powershell
# 1. YAML-Konfigs in das Seed-File konvertieren (idempotent, schreibt
#    backend/app/seed/job_sources.seed.json):
cd backend
python scripts/import_job_counter_yaml.py `
    --source ../path/to/11_JobCounter/01_JobCounter/config

# 2. Optional: Tagessnapshots aus dem alten Storage in job_snapshots
#    nachladen (idempotent durch UNIQUE(source, date)):
python scripts/import_job_counter_history.py `
    --snapshots ../path/to/11_JobCounter/01_JobCounter/data/snapshots
```

Beim ersten Start nach dem Migrate-Schritt wird `job_sources.seed.json`
automatisch geladen, solange `job_sources` leer ist (analog zur
Stocks-Seed).
