# ADR 0002: Career-portal scrape pipeline integrated as a second `run_type`

* Status: Accepted
* Date: 2026-05-03
* Context: Integration of the standalone `11_JobCounter` project into
  `CompanyTracker`.

## Context

The `11_JobCounter` project (a standalone FastAPI scraper that lived at
`11_JobCounter/01_JobCounter/` in the source tree before this ADR
removed it) scraped career portals daily and plotted "open positions"
trends per company. The two systems share a
target audience (the operator watching one watchlist) and a workflow
shape (cron-driven background scrape, time-series chart). Running them
side-by-side as separate apps duplicated:

* the auth/CSRF stack,
* the cron+lock plumbing,
* and especially the per-company configuration (the user maintained a
  YAML registry in JobCounter and an ISIN watchlist in CompanyTracker
  that referenced the same companies).

We folded the JobCounter feature into CompanyTracker with the explicit
goal of reusing the existing infrastructure rather than running a
parallel scheduler stack.

## Decision

The career-portal scrape is implemented as a **second `run_type` on the
existing `RunLog` table** rather than a parallel runs system or a new
"step" inside the market-data pipeline.

### Concrete shape

* New tables `job_sources`, `job_snapshots`, `run_job_status` (see
  [`backend/migrations/versions/0002_job_sources.py`](../../backend/migrations/versions/0002_job_sources.py)).
* `RunLog.run_type ∈ {"market", "jobs"}`. Both pipelines share the
  same lifecycle columns (`phase`, `status`, `stocks_*`) and the same
  `RefreshWorker` thread.
* `run_job_status` mirrors `run_stock_status` per source instead of
  hijacking the symbol/quote/metrics step columns of the market run.
* A separate lock name (`daily_jobs_refresh`) lets a market refresh
  and a job scrape run side-by-side. Both still go through
  `lock_manager.try_acquire_lock`, which is already process-safe.
* The cron scheduler registers two independent jobs
  (`daily_refresh`, `daily_jobs_scrape`) wired to two different
  `AppSettings` time fields. The market refresh keeps its 22:30 default,
  the job scrape defaults to 02:00 local time.
* All eight adapters from the JobCounter codebase are ported. Five run
  on `httpx` only (`static_html`, `json_get_path_int`,
  `json_get_array_count`, `json_post_path_int`, `json_post_facet_sum`)
  and ship as part of the default backend install. Three need a real
  browser (`playwright_api_fetch`, `playwright_css_count`,
  `playwright_text_regex`) and live behind the optional
  `backend[playwright]` extra so the default install does **not** pull
  ~500 MB of Chromium.
* When the `playwright` extra is missing, the registry omits the three
  adapters and `_adapter_for` raises an `AdapterError` whose message
  points at the install command. Configurations that reference a
  Playwright adapter still load (the schema layer accepts every known
  name) so they survive a temporary downgrade.
* The Chromium browser is owned by a singleton `PlaywrightPool`. It is
  launched on the first scrape and reused across sources during the
  same daily run; the FastAPI lifespan closes it on shutdown.

## Alternatives considered

1. **Bolt jobs onto the market pipeline as a fourth step.** Cheap
   table-wise, but it conflated two unrelated failure modes (market data
   broken vs. job portal broken would both surface as "run had an
   error") and forced both pipelines to share a schedule.
2. **Parallel `JobsRunLog` table.** Cleanest separation but duplicated
   the entire `phase`/`status`/`stocks_*`/cleanup-of-old-runs machinery
   and forced the UI to maintain two sets of polling hooks. The shared
   `RunLog` with a discriminator column gives us 90% of the same
   observability for ~10% of the code.
3. **External Celery/RQ pipeline for jobs.** Same trade-off as
   ADR 0001 #3: meaningful only when we genuinely outgrow a single host.

## Consequences

### Positive

* The `/runs` view, current-run banner, and refresh-cancel registry
  work for both run types out of the box.
* Existing `useCurrentRun()` callers default to `run_type=market` so
  a parallel jobs run does not gray out the market-data UI.
* The Watchlist + StockDetail can render a "Stellen" column / panel
  without a new run-tracking concept on the frontend — they just hit
  the same `/run-logs` endpoints with a `run_type` filter.
* Importing the YAML configs and historical snapshots from the legacy
  project is covered by two one-shot scripts in
  [`backend/scripts/`](../../backend/scripts/) so existing data is not lost.

### Negative

* `RunLog.stocks_*` is now overloaded: for jobs runs the counters
  represent *job sources*, not stocks. The column names stay intact
  to avoid a schema break for the market pipeline, but anyone reading
  the table needs to remember the discriminator.
* Two scheduled jobs run inside one `BackgroundScheduler`. With only
  five HTTP adapters this is a non-issue; once we re-introduce the
  Playwright-based scraper (which keeps a Chromium pool alive) we'll
  need to revisit thread fan-out.

## Re-evaluate when

* The `PlaywrightPool` becomes a serialization bottleneck. Today the
  pool launches one browser and hands out fresh contexts to a single
  scraper at a time; with 5 Playwright sources at ~10 s each the daily
  run still finishes in well under a minute. If we double that count
  or push concurrency we should add an `asyncio.Semaphore` per host
  and let the pool hand out N contexts in parallel.
* The job scrape needs to react to portal-specific rate limits (e.g.
  per-host concurrency caps). Today's pipeline serializes sources
  inside one run; a per-host semaphore would slot in next to the
  existing retry helper.
