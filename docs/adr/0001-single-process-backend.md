# ADR 0001: Single-process backend

* Status: Accepted
* Date: 2026-04-26
* Context: Architecture review (`Anforderungen.md` + audit findings)

## Context

CompanyTracker started as a single-user, self-hosted watchlist tool: one
operator, a couple dozen stocks, daily market-data refresh. The MVP was
shipped as one FastAPI process backed by SQLite, with a dedicated thread
(`RefreshWorker`) running the refresh pipeline alongside the API.

During the architectural review (cf. `plan-umsetzung.md`) we revisited
whether the single-process model still made sense and what concrete
assumptions it bakes into the codebase. The intent of this ADR is to
make those assumptions explicit so future contributors can evaluate the
cost of dropping them.

## Decision

CompanyTracker stays a **single-process backend** for the foreseeable
future. The refresh pipeline, cron scheduler, rate limiter and
cancellation registry all run inside the same Python process as the
FastAPI app. SQLite remains the default storage engine.

### What this entails

* Cancellation of a running refresh uses an in-memory `set[int]`
  guarded by a threading lock (`refresh_lock._cancelled_run_ids`). It
  only flags runs owned by the current process.
* The slowapi rate-limit on `/auth/login` (`5/minute`) uses the
  in-memory backend. Per-IP fairness is preserved as long as we run
  one instance.
* The cron job (`apscheduler.BackgroundScheduler`) is started during
  the FastAPI lifespan. With more than one instance the daily refresh
  would fire on every replica.
* Concurrency between bulk and single-stock refreshes is enforced by
  the `JobLock` table in SQLite (`lock_manager.try_acquire_lock`). That
  primitive is **already** safe across processes: the rest of the
  per-process state (cancellation, rate limiter, cron) is what locks
  us into the single-process model.

## Consequences

### Positive

* The deployment surface is tiny: one container, one volume, one
  cron-bearing process. Backups are a single SQLite file.
* No external dependencies for queues / locks / rate-limit storage.
* Refresh state changes are observable in real time without a
  pub/sub bus — the worker writes straight to the same DB the API
  reads from.

### Negative / Limitations

* **No horizontal scaling.** Running two backend replicas behind a
  load balancer breaks cancellation, doubles the cron job, and
  silently raises the login rate limit by `N`. The job lock would
  still prevent corruption but wasted market-data quota is real.
* **SQLite write contention.** Long-running refreshes hold the
  database busy. The only relief valve is the per-stock commit
  cadence (4 commits per stock since the audit) — Postgres would
  scale further.
* **Single point of failure.** A crash in the worker thread takes
  down the API; we restart the whole process to recover. The
  `recover_stale_locks` startup hook makes this safe but visible to
  users.

## Alternatives considered

1. **Dedicated worker process per node, API per node.** Cleaner
   separation, but doubles the deployment artifacts and complicates
   local dev. The benefit is small while we run on a single host.
2. **External job queue (Celery / RQ + Redis).** Pays for itself
   only when we genuinely need horizontal scale; until then it
   doubles the moving parts and the failure modes (queue eviction,
   lost heartbeats, Redis backups).
3. **Multi-instance with shared Redis for state.** Required for
   true horizontal scale. We list the migration steps in the README
   under "When you need to scale out" but defer the work until a
   user-facing reason exists.

## Re-evaluate when

* The watchlist outgrows a single host's market-data quota.
* `RUNS` table writes become a bottleneck (e.g. > 5 refreshes / sec).
* Stakeholders need true HA (zero downtime during deploys).

At that point the smallest viable next step is:

1. Move state stores to Redis (`slowapi`, cancel registry).
2. Run cron in exactly one place (e.g. a `--scheduler-only` process).
3. Migrate to Postgres (the `ON CONFLICT DO NOTHING` in
   `lock_manager.py` is already SQL-standard, just confirm
   `try_acquire_lock` semantics on the new engine).
