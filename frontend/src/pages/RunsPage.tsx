import { ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { Spinner } from "../components/Spinner";
import {
  useCancelRefreshAll,
  useTriggerRefreshAll,
} from "../hooks/useStockMutations";
import {
  nextPollInterval,
  phaseLabel,
  runStatusLabel,
  STEP_STATUS_LABEL,
} from "../lib/runProgress";
import {
  RunStep,
  RunStockStatus,
  RunSummary,
  StepStatus,
} from "../types/run";

const STEP_LABELS: Record<keyof Pick<RunStockStatus, "symbol" | "quote" | "metrics">, string> = {
  symbol: "Symbol",
  quote: "Kurs",
  metrics: "Kennzahlen",
};

function StepBadge({ status }: { status: StepStatus }) {
  return <span className={`run-badge run-badge-${status}`}>{STEP_STATUS_LABEL[status]}</span>;
}

function StepCell({ step, label }: { step: RunStep; label: string }) {
  return (
    <div className="run-step-cell" title={step.error ?? undefined}>
      <span className="run-step-label">{label}</span>
      <StepBadge status={step.status as StepStatus} />
      {step.error && <span className="run-step-error">{step.error}</span>}
    </div>
  );
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "medium" });
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}

function liveDuration(run: RunSummary): number {
  if (run.duration_seconds && run.phase === "finished") return run.duration_seconds;
  if (!run.started_at) return 0;
  const startedMs = new Date(run.started_at).getTime();
  if (Number.isNaN(startedMs)) return run.duration_seconds || 0;
  const endMs = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  return Math.max(0, Math.round((endMs - startedMs) / 1000));
}

function formatStockDuration(s: RunStockStatus): string {
  if (!s.started_at) return "—";
  const start = new Date(s.started_at).getTime();
  const end = s.finished_at ? new Date(s.finished_at).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "—";
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  return formatDuration(seconds);
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
      className={`run-filter-pill${active ? " is-active" : ""}${accent ? ` run-filter-${accent}` : ""}`}
      onClick={onClick}
    >
      <span>{children}</span>
      <span className="run-filter-count">{count}</span>
    </button>
  );
}

export function RunsPage() {
  const queryClient = useQueryClient();
  const triggerRefresh = useTriggerRefreshAll();
  const cancelRefresh = useCancelRefreshAll();
  const [showHistory, setShowHistory] = useState(false);
  const [filter, setFilter] = useState<
    "all" | "running" | "error" | "done" | "not_started" | "cancelled"
  >("all");

  // Track how often we've polled the current run so we can back off the
  // refetch interval for long-running jobs.
  const tickRef = useRef(0);

  const currentQuery = useQuery<RunSummary | null>({
    queryKey: ["run-current"],
    queryFn: async () => (await api.get("/run-logs/current")).data,
    refetchInterval: (query) => {
      const data = query.state.data as RunSummary | null | undefined;
      if (!data || data.phase === "finished") {
        tickRef.current = 0;
        return false;
      }
      const next = nextPollInterval(tickRef.current);
      tickRef.current += 1;
      return next;
    },
    placeholderData: keepPreviousData,
  });
  const current = currentQuery.data ?? null;
  const runId = current?.id ?? null;
  const isRunning = current?.phase !== "finished" && current != null;

  const stocksQuery = useQuery<RunStockStatus[]>({
    queryKey: ["run-stocks", runId],
    queryFn: async () =>
      runId == null ? [] : (await api.get(`/run-logs/${runId}/stocks`)).data,
    enabled: runId != null,
    refetchInterval: (query) => {
      if (!isRunning) return false;
      // Reuse the same backoff as the summary so the two queries stay in sync.
      return nextPollInterval(Math.max(0, tickRef.current - 1));
    },
    placeholderData: keepPreviousData,
  });

  const historyQuery = useQuery<RunSummary[]>({
    queryKey: ["run-logs"],
    queryFn: async () => (await api.get("/run-logs")).data,
    enabled: showHistory,
  });

  const lastPhaseRef = useRef<string | null>(null);
  useEffect(() => {
    if (!current) return;
    if (lastPhaseRef.current !== "finished" && current.phase === "finished") {
      queryClient.invalidateQueries({ queryKey: ["stocks"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      // The per-stock backoff stops the moment phase=finished, so the last
      // poll usually still shows steps as `running`/`not_started`. Force a
      // final refetch so the UI matches what a manual reload would show.
      queryClient.invalidateQueries({ queryKey: ["run-stocks", current.id] });
    }
    lastPhaseRef.current = current.phase;
  }, [current?.phase, current, queryClient]);

  const stocks = stocksQuery.data ?? [];
  const counters = useMemo(() => {
    const c: Record<StepStatus, number> = {
      not_started: 0,
      running: 0,
      done: 0,
      error: 0,
      cancelled: 0,
    };
    for (const s of stocks) c[s.overall_status as StepStatus] = (c[s.overall_status as StepStatus] ?? 0) + 1;
    return c;
  }, [stocks]);

  const filteredStocks = useMemo(() => {
    if (filter === "all") return stocks;
    return stocks.filter((s) => s.overall_status === filter);
  }, [stocks, filter]);

  if (currentQuery.isLoading && !current) {
    return (
      <div className="page">
        <Spinner label="Lade Laufstatus…" />
      </div>
    );
  }

  if (!current) {
    return (
      <div className="page">
        <header className="page-header">
          <div className="page-header-title">
            <h2>Laufstatus</h2>
          </div>
          <div className="page-header-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => triggerRefresh.mutate()}
              disabled={triggerRefresh.isPending}
            >
              Jetzt aktualisieren
            </button>
          </div>
        </header>
        <p>Es wurde noch kein Lauf gestartet.</p>
      </div>
    );
  }

  // Single-stock refreshes share the same RunLog plumbing as the bulk job, but
  // their progress belongs on the stock detail page – here we only point at it
  // so this view stays focused on the bulk pipeline.
  if (current.stocks_total === 1) {
    const singleStock = stocks[0];
    return (
      <div className="page">
        <header className="page-header">
          <div className="page-header-title">
            <h2>Laufstatus</h2>
          </div>
          <div className="page-header-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={() => triggerRefresh.mutate()}
              disabled={isRunning || triggerRefresh.isPending}
              title={isRunning ? "Es läuft bereits ein Update" : "Jetzt aktualisieren"}
            >
              {isRunning ? "Läuft…" : "Jetzt aktualisieren"}
            </button>
          </div>
        </header>
        <p>
          {isRunning ? "Aktuell läuft ein Einzel-Refresh" : "Letzter Lauf war ein Einzel-Refresh"}
          {singleStock ? (
            <>
              {" für "}
              <Link to={`/stocks/${singleStock.isin}`} className="breadcrumb-link">
                {singleStock.stock_name || singleStock.isin}
              </Link>
              {". Fortschritt und Ergebnis stehen auf der Detailseite."}
            </>
          ) : (
            ". Fortschritt und Ergebnis stehen auf der Detailseite des Unternehmens."
          )}
        </p>
      </div>
    );
  }

  const total = current.stocks_total || 0;
  const done = current.stocks_done || 0;
  const progressPct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div className="page">
      <header className="page-header">
        <div className="page-header-title">
          <h2>
            Laufstatus
            <span className="muted-count">
              {" "}
              · Run #{current.id} · {phaseLabel(current.phase)}
            </span>
          </h2>
        </div>
        <div className="page-header-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? "Historie ausblenden" : "Historie anzeigen"}
          </button>
          {isRunning && (
            <button
              type="button"
              className="btn-danger"
              onClick={() => cancelRefresh.mutate()}
              disabled={cancelRefresh.isPending}
              title="Den laufenden Update-Job abbrechen"
            >
              {cancelRefresh.isPending ? "Wird abgebrochen…" : "Lauf abbrechen"}
            </button>
          )}
          <button
            type="button"
            className="btn-primary"
            onClick={() => triggerRefresh.mutate()}
            disabled={isRunning || triggerRefresh.isPending}
            title={isRunning ? "Es läuft bereits ein Update" : "Jetzt aktualisieren"}
          >
            {isRunning ? "Läuft…" : "Jetzt aktualisieren"}
          </button>
        </div>
      </header>

      <div className="run-summary-card">
        <div className="run-summary-grid">
          <RunSummaryItem label="Phase" value={phaseLabel(current.phase)} accent={current.phase} />
          <RunSummaryItem label="Status" value={runStatusLabel(current.status)} accent={current.status} />
          <RunSummaryItem label="Start" value={formatDateTime(current.started_at)} />
          <RunSummaryItem
            label={current.phase === "finished" ? "Ende" : "Bisher"}
            value={
              current.phase === "finished"
                ? formatDateTime(current.finished_at)
                : formatDuration(liveDuration(current))
            }
          />
          <RunSummaryItem label="Fortschritt" value={`${done} / ${total}`} sub={`${progressPct} %`} />
          <RunSummaryItem label="Erfolge" value={String(current.stocks_success)} accent="done" />
          <RunSummaryItem
            label="Fehler"
            value={String(current.stocks_error)}
            accent={current.stocks_error ? "error" : undefined}
          />
        </div>
        <div className="run-progress-bar" aria-label={`${progressPct} %`}>
          <div className="run-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        {current.error_details && (
          <details className="run-error-details">
            <summary>Fehler-Details ({current.stocks_error})</summary>
            <pre>{current.error_details}</pre>
          </details>
        )}
      </div>

      <div className="run-filter-row">
        <FilterPill active={filter === "all"} onClick={() => setFilter("all")} count={stocks.length}>
          Alle
        </FilterPill>
        <FilterPill
          active={filter === "running"}
          onClick={() => setFilter("running")}
          count={counters.running}
          accent="running"
        >
          Läuft
        </FilterPill>
        <FilterPill active={filter === "done"} onClick={() => setFilter("done")} count={counters.done} accent="done">
          Fertig
        </FilterPill>
        <FilterPill
          active={filter === "error"}
          onClick={() => setFilter("error")}
          count={counters.error}
          accent="error"
        >
          Fehler
        </FilterPill>
        <FilterPill
          active={filter === "not_started"}
          onClick={() => setFilter("not_started")}
          count={counters.not_started}
          accent="not_started"
        >
          Wartet
        </FilterPill>
        {counters.cancelled > 0 && (
          <FilterPill
            active={filter === "cancelled"}
            onClick={() => setFilter("cancelled")}
            count={counters.cancelled}
            accent="cancelled"
          >
            Abgebrochen
          </FilterPill>
        )}
      </div>

      <div className="run-table-wrapper">
        {filteredStocks.length === 0 ? (
          <p className="run-empty">Keine Einträge in dieser Auswahl.</p>
        ) : (
          <table className="run-table">
            <thead>
              <tr>
                <th>Unternehmen</th>
                <th>Gesamt</th>
                <th>Symbol</th>
                <th>Kurs</th>
                <th>Kennzahlen</th>
                <th>Dauer</th>
              </tr>
            </thead>
            <tbody>
              {filteredStocks.map((s) => (
                <tr key={s.isin} className={`run-row run-row-${s.overall_status}`}>
                  <td>
                    <div className="run-stock-name">{s.stock_name || s.isin}</div>
                    <div className="run-stock-meta">
                      <span className="isin-pill">{s.isin}</span>
                      {s.resolved_symbol && <span className="run-symbol">{s.resolved_symbol}</span>}
                    </div>
                  </td>
                  <td>
                    <StepBadge status={s.overall_status as StepStatus} />
                  </td>
                  <td>
                    <StepCell step={s.symbol} label={STEP_LABELS.symbol} />
                  </td>
                  <td>
                    <StepCell step={s.quote} label={STEP_LABELS.quote} />
                  </td>
                  <td>
                    <StepCell step={s.metrics} label={STEP_LABELS.metrics} />
                  </td>
                  <td className="run-duration">{formatStockDuration(s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showHistory && (
        <section className="run-history">
          <h3>Historie</h3>
          {historyQuery.isLoading ? (
            <Spinner label="Lade Historie…" />
          ) : (
            <table className="run-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Start</th>
                  <th>Phase</th>
                  <th>Status</th>
                  <th>Dauer</th>
                  <th>OK / Fehler / Gesamt</th>
                </tr>
              </thead>
              <tbody>
                {(historyQuery.data ?? []).map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>{formatDateTime(r.started_at)}</td>
                    <td>{phaseLabel(r.phase)}</td>
                    <td>{runStatusLabel(r.status)}</td>
                    <td>{formatDuration(r.duration_seconds)}</td>
                    <td>
                      {r.stocks_success} / {r.stocks_error} / {r.stocks_total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}
