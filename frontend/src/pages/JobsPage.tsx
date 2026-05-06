import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Spinner } from "../components/Spinner";
import { CreateStockModal } from "../components/watchlist/CreateStockModal";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  JOB_SOURCES_KEY,
  useCancelJobsRefresh,
  useJobSources,
  useRefreshAllJobs,
  useRefreshJobSource,
  useRunJobStatuses,
} from "../hooks/useJobSources";
import { STOCKS_LIST_KEY } from "../hooks/useStockMutations";
import { useStocks } from "../hooks/useStockQueries";
import { extractApiError } from "../lib/apiError";
import {
  formatDateOnly,
  formatDateTime,
  formatDuration,
  parseBackendDate,
} from "../lib/format";
import {
  liveRunSeconds,
  phaseLabel,
  runStatusLabel,
  STEP_STATUS_LABEL,
  useCurrentRun,
} from "../lib/runProgress";
import { toast } from "../lib/toast";
import type { JobSource, RunJobStatus } from "../types/jobs";
import type { StepStatus } from "../types/run";

type Filter = "all" | "active" | "inactive";
type LiveFilter = "all" | StepStatus;

function deltaClass(delta: number | null | undefined): string {
  if (delta == null || delta === 0) return "";
  return delta > 0 ? "delta-up" : "delta-down";
}

function formatDelta(delta: number | null | undefined): string {
  if (delta == null) return "–";
  if (delta === 0) return "0";
  return delta > 0 ? `+${delta}` : `${delta}`;
}

// Live duration of a single source row in seconds. Mirrors `liveStockSeconds`
// but works on the lighter `RunJobStatus` shape (only `started_at`/`finished_at`).
// Backend ships naive UTC strings; `parseBackendDate` normalises them so the
// counter does not skew by the host's UTC offset.
function liveSourceSeconds(
  startedAt: string | null,
  finishedAt: string | null
): number | null {
  if (!startedAt) return null;
  const start = parseBackendDate(startedAt).getTime();
  const end = finishedAt ? parseBackendDate(finishedAt).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, Math.round((end - start) / 1000));
}

function RunSummaryItem({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className={`run-summary-item${accent ? ` run-summary-${accent}` : ""}`}>
      <div className="run-summary-label">{label}</div>
      <div className="run-summary-value">{value}</div>
      {sub && <div className="run-summary-sub">{sub}</div>}
    </div>
  );
}

function FilterPill({
  active,
  count,
  accent,
  onClick,
  children,
}: {
  active: boolean;
  count: number;
  accent?: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`run-filter-pill${active ? " is-active" : ""}${
        accent ? ` run-filter-${accent}` : ""
      }`}
      onClick={onClick}
    >
      <span>{children}</span>
      <span className="run-filter-count">{count}</span>
    </button>
  );
}

export function JobsPage() {
  useDocumentTitle("Stellen");
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const isinFilter = params.get("isin");
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [liveFilter, setLiveFilter] = useState<LiveFilter>("all");

  // Live run state for the jobs pipeline. `useCurrentRun("jobs")` falls back to
  // its own polling subscription (the shared CurrentRunProvider only handles
  // the market run), so this kicks off the 1.5s backoff as soon as a refresh
  // starts and stops on its own once `phase === "finished"`.
  const { data: currentRun } = useCurrentRun("jobs");
  const isRunning = currentRun != null && currentRun.phase !== "finished";
  const runId = currentRun?.id ?? null;

  const sourcesQuery = useJobSources({
    isin: isinFilter,
    is_active: filter === "all" ? null : filter === "active",
  }, { polling: isRunning });
  const refreshAll = useRefreshAllJobs();
  const cancelAll = useCancelJobsRefresh();
  const refreshSource = useRefreshJobSource();
  const { data: jobStatuses } = useRunJobStatuses(
    runId ?? undefined,
    isRunning
  );

  // Load the watchlist to determine which ISINs are already tracked.
  const stocksQuery = useStocks();
  const isinSet = useMemo<Set<string>>(() => {
    const stocks = stocksQuery.data ?? [];
    return new Set(stocks.map((s) => s.isin));
  }, [stocksQuery.data]);

  const sources = useMemo(() => sourcesQuery.data ?? [], [sourcesQuery.data]);
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return sources;
    return sources.filter(
      (s) =>
        s.name.toLowerCase().includes(term) ||
        (s.isin ?? "").toLowerCase().includes(term)
    );
  }, [sources, search]);

  const statusByJobId = useMemo(() => {
    const m = new Map<number, RunJobStatus>();
    for (const r of jobStatuses ?? []) m.set(r.job_source_id, r);
    return m;
  }, [jobStatuses]);

  // Counters for the live filter pills. We always look at the *visible*
  // sources (after the static toolbar filters apply) so the counts match the
  // table the user sees.
  const liveCounters = useMemo(() => {
    const c: Record<StepStatus, number> = {
      not_started: 0,
      running: 0,
      done: 0,
      error: 0,
      cancelled: 0,
    };
    for (const s of filtered) {
      const st = statusByJobId.get(s.id);
      if (!st) continue;
      const key = st.overall_status as StepStatus;
      c[key] = (c[key] ?? 0) + 1;
    }
    return c;
  }, [filtered, statusByJobId]);

  const visibleSources = useMemo(() => {
    if (!currentRun || liveFilter === "all") return filtered;
    return filtered.filter(
      (s) => statusByJobId.get(s.id)?.overall_status === liveFilter
    );
  }, [filtered, currentRun, liveFilter, statusByJobId]);

  // Re-render every second while a run is active so the live duration counters
  // (`liveSourceSeconds` for the row, `liveRunSeconds` for the summary) keep
  // ticking in between API polls.
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  // When a run flips to finished, the per-source `latest_count` /
  // `latest_snapshot_date` / `delta_*` derived fields on `/job-sources` change
  // — but that endpoint is only re-fetched when its query gets invalidated.
  // Trigger it once on the running→finished transition.
  const lastPhaseRef = useRef<string | null>(null);
  useEffect(() => {
    if (!currentRun) return;
    if (lastPhaseRef.current !== "finished" && currentRun.phase === "finished") {
      qc.invalidateQueries({ queryKey: JOB_SOURCES_KEY });
      qc.invalidateQueries({ queryKey: ["stock-jobs"] });
    }
    lastPhaseRef.current = currentRun.phase;
  }, [currentRun, qc]);

  // Reset the live filter when no run is active so it does not "hide" rows
  // on the next render once the summary card disappears.
  useEffect(() => {
    if (!currentRun) setLiveFilter("all");
  }, [currentRun]);

  const handleRefreshAll = () =>
    refreshAll.mutate(undefined, {
      onSuccess: (res) => {
        if (res.status === "started") {
          toast.success("Jobs-Aktualisierung gestartet.");
        } else if (res.status === "already_running") {
          toast.info("Es läuft bereits eine Jobs-Aktualisierung.");
        } else if (res.status === "skipped") {
          toast.info("Jobs-Aktualisierung ist deaktiviert (Settings).");
        }
      },
      onError: (err) =>
        toast.error(extractApiError(err, "Aktualisierung konnte nicht gestartet werden.")),
    });

  const handleCancel = () =>
    cancelAll.mutate(undefined, {
      onSuccess: (res) => {
        if (res.cancelled) toast.success("Lauf wird abgebrochen.");
        else toast.info("Kein laufender Lauf zum Abbrechen.");
      },
      onError: (err) =>
        toast.error(extractApiError(err, "Abbruch fehlgeschlagen.")),
    });

  const handleRefreshSource = (source: JobSource) =>
    refreshSource.mutate(source.id, {
      onSuccess: (res) => {
        if (res.status === "started") {
          toast.success(`Aktualisierung für ${source.name} gestartet.`);
        } else if (res.status === "already_running") {
          toast.info("Eine andere Job-Aktualisierung läuft bereits.");
        }
      },
      onError: (err) =>
        toast.error(extractApiError(err, "Aktualisierung konnte nicht gestartet werden.")),
    });

  // Watchlist-add state: which JobSource the user wants to add to the watchlist.
  const [watchlistTarget, setWatchlistTarget] = useState<JobSource | null>(null);

  function handleOpenAddToWatchlist(source: JobSource) {
    setWatchlistTarget(source);
  }

  async function handleStockCreated() {
    await qc.invalidateQueries({ queryKey: STOCKS_LIST_KEY });
  }

  if (sourcesQuery.isLoading) {
    return (
      <div className="page">
        <Spinner label="Lade Karriereportal-Quellen…" />
      </div>
    );
  }

  const total = currentRun?.stocks_total ?? 0;
  const done = currentRun?.stocks_done ?? 0;
  const progressPct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div className="page">
      <header className="page-header">
        <div className="page-header-title">
          <h2>
            Stellen
            <span className="muted-count">
              {" "}· Karriereportal-Quellen · {filtered.length}/{sources.length}
            </span>
            {currentRun && (
              <span className="muted-count">
                {" "}· Run #{currentRun.id} · {phaseLabel(currentRun.phase)}
              </span>
            )}
          </h2>
        </div>
        <div className="page-header-actions">
          <Link to="/jobs/new" className="btn-secondary">
            Neue Quelle
          </Link>
          <button
            type="button"
            className="btn-danger"
            onClick={handleCancel}
            disabled={!isRunning || cancelAll.isPending}
            title={isRunning ? "Aktiven Lauf abbrechen" : "Kein Lauf aktiv"}
          >
            {cancelAll.isPending ? "Abbruch…" : "Lauf abbrechen"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleRefreshAll}
            disabled={isRunning || refreshAll.isPending}
            title={isRunning ? "Es läuft bereits ein Update" : "Jetzt aktualisieren"}
          >
            {isRunning ? "Läuft…" : "Alle aktualisieren"}
          </button>
        </div>
      </header>

      {currentRun && (
        <div className="run-summary-card">
          <div className="run-summary-grid">
            <RunSummaryItem
              label="Phase"
              value={phaseLabel(currentRun.phase)}
              accent={currentRun.phase}
            />
            <RunSummaryItem
              label="Status"
              value={runStatusLabel(currentRun.status)}
              accent={currentRun.status}
            />
            <RunSummaryItem label="Start" value={formatDateTime(currentRun.started_at)} />
            <RunSummaryItem
              label={currentRun.phase === "finished" ? "Ende" : "Bisher"}
              value={
                currentRun.phase === "finished"
                  ? formatDateTime(currentRun.finished_at)
                  : formatDuration(liveRunSeconds(currentRun), { dashOnZero: false })
              }
            />
            <RunSummaryItem
              label="Fortschritt"
              value={`${done} / ${total}`}
              sub={`${progressPct} %`}
            />
            <RunSummaryItem
              label="Erfolge"
              value={String(currentRun.stocks_success)}
              accent="done"
            />
            <RunSummaryItem
              label="Fehler"
              value={String(currentRun.stocks_error)}
              accent={currentRun.stocks_error ? "error" : undefined}
            />
          </div>
          <div className="run-progress-bar" aria-label={`${progressPct} %`}>
            <div className="run-progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          {currentRun.error_details && (
            <details className="run-error-details">
              <summary>Fehler-Details ({currentRun.stocks_error})</summary>
              <pre>{currentRun.error_details}</pre>
            </details>
          )}
        </div>
      )}

      {currentRun && (
        <div className="run-filter-row">
          <FilterPill
            active={liveFilter === "all"}
            onClick={() => setLiveFilter("all")}
            count={filtered.length}
          >
            Alle
          </FilterPill>
          <FilterPill
            active={liveFilter === "running"}
            onClick={() => setLiveFilter("running")}
            count={liveCounters.running}
            accent="running"
          >
            Läuft
          </FilterPill>
          <FilterPill
            active={liveFilter === "done"}
            onClick={() => setLiveFilter("done")}
            count={liveCounters.done}
            accent="done"
          >
            Fertig
          </FilterPill>
          <FilterPill
            active={liveFilter === "error"}
            onClick={() => setLiveFilter("error")}
            count={liveCounters.error}
            accent="error"
          >
            Fehler
          </FilterPill>
          <FilterPill
            active={liveFilter === "not_started"}
            onClick={() => setLiveFilter("not_started")}
            count={liveCounters.not_started}
            accent="not_started"
          >
            Wartet
          </FilterPill>
          {liveCounters.cancelled > 0 && (
            <FilterPill
              active={liveFilter === "cancelled"}
              onClick={() => setLiveFilter("cancelled")}
              count={liveCounters.cancelled}
              accent="cancelled"
            >
              Abgebrochen
            </FilterPill>
          )}
        </div>
      )}

      <div className="jobs-toolbar">
        <div className="jobs-toolbar-filters">
          <button
            type="button"
            className={`run-filter-pill${filter === "all" ? " is-active" : ""}`}
            onClick={() => setFilter("all")}
          >
            Alle <span className="run-filter-count">{sources.length}</span>
          </button>
          <button
            type="button"
            className={`run-filter-pill${filter === "active" ? " is-active" : ""}`}
            onClick={() => setFilter("active")}
          >
            Aktiv
          </button>
          <button
            type="button"
            className={`run-filter-pill${filter === "inactive" ? " is-active" : ""}`}
            onClick={() => setFilter("inactive")}
          >
            Inaktiv
          </button>
        </div>
        <input
          type="search"
          className="form-input"
          placeholder="Filtern (Name oder ISIN)"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isinFilter && (
        <p className="run-empty">
          Gefiltert nach ISIN <strong>{isinFilter}</strong>.{" "}
          <Link to="/jobs">Filter aufheben</Link>
        </p>
      )}

      <div className="run-table-wrapper">
        {visibleSources.length === 0 ? (
          <p className="run-empty">Keine Quellen gefunden.</p>
        ) : (
          <table className="jobs-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Adapter</th>
                <th>ISIN</th>
                <th style={{ textAlign: "right" }}>Aktuell</th>
                <th style={{ textAlign: "right" }}>Δ 7T</th>
                <th style={{ textAlign: "right" }}>Δ 30T</th>
                <th>Stand</th>
                <th>Lauf-Status</th>
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {visibleSources.map((source) => {
                const status = statusByJobId.get(source.id);
                const liveStatus = (
                  status?.overall_status ??
                  (currentRun && currentRun.stocks_total > 1 ? "not_started" : null)
                ) as StepStatus | null;
                const isRowRunning = liveStatus === "running";
                const otherRowRunning = isRunning && !isRowRunning;
                const rowClass = liveStatus
                  ? `run-row run-row-${liveStatus}`
                  : "run-row";
                return (
                  <tr key={source.id} className={rowClass}>
                    <td>
                      <div className="run-stock-name">
                        <Link to={`/jobs/${source.id}`} className="breadcrumb-link">
                          {source.name}
                        </Link>
                      </div>
                      <div className="run-stock-meta">
                        {source.is_active ? (
                          <span className="badge run-badge-done">aktiv</span>
                        ) : (
                          <span className="badge badge-muted">inaktiv</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <code style={{ fontSize: 12 }}>{source.adapter_type}</code>
                    </td>
                    <td>
                      {source.isin ? (
                        isinSet.has(source.isin) ? (
                          <Link to={`/stocks/${source.isin}`} className="breadcrumb-link">
                            {source.isin}
                          </Link>
                        ) : (
                          <button
                            type="button"
                            className="btn-secondary btn-sm"
                            onClick={() => handleOpenAddToWatchlist(source)}
                            disabled={stocksQuery.isLoading}
                            title={`${source.isin} zur Watchlist hinzufügen`}
                            aria-label={`${source.isin} zur Watchlist hinzufügen`}
                          >
                            {source.isin}{" "}
                            <span className="watchlist-add-icon" aria-hidden="true">＋</span>
                          </button>
                        )
                      ) : (
                        <span className="muted-count">–</span>
                      )}
                    </td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>
                      {source.latest_count != null ? source.latest_count : "–"}
                    </td>
                    <td
                      style={{ textAlign: "right" }}
                      className={deltaClass(source.delta_7d)}
                    >
                      {formatDelta(source.delta_7d)}
                    </td>
                    <td
                      style={{ textAlign: "right" }}
                      className={deltaClass(source.delta_30d)}
                    >
                      {formatDelta(source.delta_30d)}
                    </td>
                    <td>{formatDateOnly(source.latest_snapshot_date)}</td>
                    <td>
                      {liveStatus ? (
                        <div className="run-step-cell" title={status?.error ?? undefined}>
                          <span
                            className={`run-badge run-badge-${liveStatus}`}
                          >
                            {STEP_STATUS_LABEL[liveStatus]}
                          </span>
                          {status?.started_at && (
                            <span className="run-duration">
                              {formatDuration(
                                liveSourceSeconds(
                                  status.started_at,
                                  status.finished_at
                                ),
                                { dashOnZero: false }
                              )}
                            </span>
                          )}
                          {status?.error && (
                            <span className="run-step-error">{status.error}</span>
                          )}
                        </div>
                      ) : (
                        <span className="muted-count">–</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => handleRefreshSource(source)}
                        disabled={
                          refreshSource.isPending || otherRowRunning || isRowRunning
                        }
                        title={
                          isRowRunning
                            ? "Diese Quelle wird gerade aktualisiert"
                            : otherRowRunning
                            ? "Ein Jobs-Lauf läuft bereits"
                            : "Diese Quelle einzeln aktualisieren"
                        }
                      >
                        Aktualisieren
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <CreateStockModal
        open={watchlistTarget !== null}
        onClose={() => setWatchlistTarget(null)}
        tagSuggestions={[]}
        onCreated={handleStockCreated}
        initialValues={
          watchlistTarget
            ? { isin: watchlistTarget.isin ?? "", name: watchlistTarget.name }
            : undefined
        }
      />
    </div>
  );
}

export default JobsPage;
