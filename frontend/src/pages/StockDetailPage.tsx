import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { Spinner } from "../components/Spinner";

// AI panel lazy-loads in its own chunk so the much smaller "Kursverlauf +
// Kennzahlen + Audit"-Block above the fold can paint immediately while the
// (relatively big) AI bundle is still downloading.
const AIAgentsPanel = lazy(() =>
  import("../components/ai/AIAgentsPanel").then((m) => ({ default: m.AIAgentsPanel }))
);
import {
  RefreshKickoff,
  STOCKS_QUERY_KEY,
  useDeleteStock,
  useRefreshStock,
} from "../hooks/useStockMutations";
import { useChartTheme } from "../hooks/useChartTheme";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useStock, useStockHistory, useStockPeers } from "../hooks/useStockQueries";
import { extractApiError } from "../lib/apiError";
import {
  changeClass,
  defaultThresholds,
  dividendClass,
  equityRatioClass,
  targetClass,
} from "../lib/colorRules";
import { confirm } from "../lib/dialogs";
import { toast } from "../lib/toast";
import {
  formatCurrency,
  formatDate,
  formatDuration,
  formatLargeCurrency,
  formatNumber,
  formatPercent,
  formatTimeShort,
} from "../lib/format";
import {
  liveRunSeconds,
  nextPollInterval,
  phaseLabel,
  STEP_STATUS_LABEL,
  useCurrentRun,
} from "../lib/runProgress";
import { tagColorClass } from "../lib/tagColor";
import type { HistoryRange, Stock } from "../types";
import type { RunStockStatus, StepStatus } from "../types/run";

const RANGE_LABELS: { key: HistoryRange; label: string }[] = [
  { key: "1m", label: "1M" },
  { key: "6m", label: "6M" },
  { key: "1y", label: "1J" },
  { key: "5y", label: "5J" },
  { key: "max", label: "Max" },
];

const VALID_RANGES = new Set<HistoryRange>(["1m", "6m", "1y", "5y", "max"]);
const DEFAULT_RANGE: HistoryRange = "1y";

function parseRangeParam(value: string | null): HistoryRange {
  if (value && VALID_RANGES.has(value as HistoryRange)) {
    return value as HistoryRange;
  }
  return DEFAULT_RANGE;
}

interface KpiTileProps {
  label: string;
  value: string;
  sub?: string;
  className?: string;
}

function KpiTile({ label, value, sub, className }: KpiTileProps) {
  return (
    <div className={`run-summary-item ${className ?? ""}`.trim()}>
      <div className="run-summary-label">{label}</div>
      <div className="run-summary-value">{value}</div>
      {sub && <div className="run-summary-sub">{sub}</div>}
    </div>
  );
}

interface HistoryChartProps {
  isin: string;
  stock: Stock;
}

function HistoryChart({ isin, stock }: HistoryChartProps) {
  // Persist the chosen range in `?range=…` so deep links to a detail page
  // restore the user's preferred zoom level. Anything unknown / missing falls
  // back to the default.
  const [searchParams, setSearchParams] = useSearchParams();
  const range = parseRangeParam(searchParams.get("range"));
  const setRange = (next: HistoryRange) => {
    const params = new URLSearchParams(searchParams);
    if (next === DEFAULT_RANGE) {
      params.delete("range");
    } else {
      params.set("range", next);
    }
    setSearchParams(params, { replace: true });
  };
  const historyQuery = useStockHistory(isin, range);
  const points = historyQuery.data?.points ?? [];
  const chartTheme = useChartTheme();

  const chartData = useMemo(
    () =>
      points
        .filter((p) => p.close !== null && p.date)
        .map((p) => ({
          date: p.date,
          close: p.close ?? 0,
          high: p.high,
          low: p.low,
        })),
    [points]
  );

  const numericRefLines: { value: number; label: string; color: string }[] = [];
  if (stock.analyst_target_1y != null)
    numericRefLines.push({ value: stock.analyst_target_1y, label: "Kursziel", color: "#059669" });

  const yDomain = useMemo<[number | "auto", number | "auto"]>(() => {
    if (chartData.length === 0) return ["auto", "auto"];
    const values = chartData
      .flatMap((p) => [p.close, p.high ?? p.close, p.low ?? p.close])
      .filter((v): v is number => v !== null && v !== undefined);
    if (values.length === 0) return ["auto", "auto"];
    let min = Math.min(...values);
    let max = Math.max(...values);
    for (const r of numericRefLines) {
      min = Math.min(min, r.value);
      max = Math.max(max, r.value);
    }
    const pad = (max - min) * 0.05 || max * 0.05 || 1;
    return [Math.max(0, min - pad), max + pad];
  }, [chartData, numericRefLines]);

  return (
    <div className="detail-card detail-chart-card">
      <div className="detail-chart-header">
        <h3>Kursverlauf</h3>
        <div className="detail-chart-tabs" role="tablist" aria-label="Zeitraum">
          {RANGE_LABELS.map((r) => (
            <button
              key={r.key}
              type="button"
              role="tab"
              aria-selected={range === r.key}
              className={`chart-range-pill ${range === r.key ? "is-active" : ""}`.trim()}
              onClick={() => setRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      {historyQuery.isLoading && <Spinner label="Lade Kursverlauf..." />}
      {!historyQuery.isLoading && chartData.length === 0 && (
        <div className="detail-chart-empty">
          Keine Historie verfügbar. Provider liefert für dieses Symbol aktuell keine Kursreihe.
        </div>
      )}
      {chartData.length > 0 && (
        <>
          <div className="detail-chart-body">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 8, right: 64, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={chartTheme.grid} vertical={false} />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value: string) => {
                    const d = new Date(value);
                    if (range === "1m" || range === "6m")
                      return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
                    if (range === "1y" || range === "5y")
                      return d.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
                    return d.toLocaleDateString("de-DE", { year: "numeric" });
                  }}
                  minTickGap={32}
                  tick={{ fontSize: 11, fill: chartTheme.tick }}
                  stroke={chartTheme.grid}
                />
                <YAxis
                  domain={yDomain}
                  tick={{ fontSize: 11, fill: chartTheme.tick }}
                  tickFormatter={(v: number) => v.toFixed(0)}
                  width={48}
                  stroke={chartTheme.grid}
                />
                <Tooltip
                  formatter={(value) => [
                    formatCurrency(Number(value), stock.currency),
                    "Kurs",
                  ]}
                  labelFormatter={(label) =>
                    new Date(String(label)).toLocaleDateString("de-DE", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                    })
                  }
                  contentStyle={{
                    background: chartTheme.tooltipBackground,
                    border: `1px solid ${chartTheme.tooltipBorder}`,
                    color: chartTheme.tooltipText,
                  }}
                  labelStyle={{ color: chartTheme.tooltipText }}
                  itemStyle={{ color: chartTheme.tooltipText }}
                />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke={chartTheme.line}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  name="Kurs"
                />
                {numericRefLines.map((ref) => (
                  <ReferenceLine
                    key={ref.label}
                    y={ref.value}
                    stroke={ref.color}
                    strokeDasharray="4 4"
                    label={{
                      value: ref.label,
                      position: "right",
                      fill: ref.color,
                      fontSize: 11,
                    }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="detail-chart-legend">
            <span className="chart-legend-item">
              <span className="legend-swatch legend-price" /> Kurs
            </span>
            {numericRefLines.map((r) => (
              <span key={r.label} className="chart-legend-item">
                <span
                  className="legend-swatch legend-dashed"
                  style={{ background: r.color }}
                />
                {r.label} ({formatCurrency(r.value, stock.currency)})
              </span>
            ))}
          </div>
          {historyQuery.data?.fetched_at && (
            <div className="detail-chart-source">
              Cache vom {formatDate(historyQuery.data.fetched_at)} · Interval: {historyQuery.data.interval}
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface PeersProps {
  isin: string;
}

function PeersStrip({ isin }: PeersProps) {
  const peersQuery = useStockPeers(isin, 5);
  const peers = peersQuery.data ?? [];

  return (
    <div className="detail-card">
      <div className="detail-card-head">
        <h3>Ähnliche Unternehmen</h3>
        <span className="detail-card-hint">Gleicher Sektor, sortiert nach Marktkapitalisierung</span>
      </div>
      {peersQuery.isLoading && <Spinner label="Lade Vorschläge..." />}
      {!peersQuery.isLoading && peers.length === 0 && (
        <div className="detail-empty">
          Keine vergleichbaren Unternehmen in der Watchlist gefunden.
        </div>
      )}
      {peers.length > 0 && (
        <div className="peers-strip">
          {peers.map((p) => (
            <Link key={p.isin} to={`/stocks/${p.isin}`} className="peer-card">
              <div className="peer-card-head">
                <span className="peer-name">{p.name}</span>
                <span className="isin-pill">{p.isin}</span>
              </div>
              <div className="peer-card-meta">
                <span className="peer-sector">{p.sector ?? "–"}</span>
              </div>
              <div className="peer-card-stats">
                <div>
                  <span className="peer-stat-label">Kurs</span>
                  <span className="peer-stat-value">{formatCurrency(p.current_price, p.currency)}</span>
                </div>
                <div>
                  <span className="peer-stat-label">Tag</span>
                  <span className={`peer-stat-value ${changeClass(p.day_change_pct, defaultThresholds)}`}>
                    {formatPercent(p.day_change_pct)}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

interface RefreshStatusCardProps {
  isin: string;
  kickoff: RefreshKickoff | null;
}

function StepRow({ label, status, error }: { label: string; status: StepStatus; error: string | null }) {
  return (
    <div className="refresh-step-row" title={error ?? undefined}>
      <span className="refresh-step-label">{label}</span>
      <span className={`run-badge run-badge-${status}`}>{STEP_STATUS_LABEL[status]}</span>
      {error && <span className="refresh-step-error">{error}</span>}
    </div>
  );
}

// Inline status panel for the per-stock "Marktdaten aktualisieren" action.
function RefreshStatusCard({ isin, kickoff }: RefreshStatusCardProps) {
  const qc = useQueryClient();
  const { data: current } = useCurrentRun();
  const isRunning = current != null && current.phase !== "finished";
  const isSingleRun = current != null && current.stocks_total === 1;
  const runId = current?.id ?? null;

  // Local backoff tick for the per-stock query (no longer entangled with the
  // shared current-run hook).
  const stocksTickRef = useRef(0);
  const stocksQuery = useQuery<RunStockStatus[]>({
    queryKey: ["run-stocks", runId],
    queryFn: async () =>
      runId == null ? [] : (await api.get(`/run-logs/${runId}/stocks`)).data,
    enabled: runId != null && isSingleRun,
    refetchInterval: () => {
      if (!isRunning || !isSingleRun) {
        stocksTickRef.current = 0;
        return false;
      }
      const next = nextPollInterval(stocksTickRef.current);
      stocksTickRef.current += 1;
      return next;
    },
    placeholderData: keepPreviousData,
  });
  const myStock = (stocksQuery.data ?? []).find((s) => s.isin === isin) ?? null;

  const [, setNowTick] = useState(0);
  useEffect(() => {
    if (!isRunning || !isSingleRun || !myStock) return;
    const handle = window.setInterval(() => setNowTick((t) => t + 1), 1000);
    return () => window.clearInterval(handle);
  }, [isRunning, isSingleRun, myStock]);

  const lastPhaseRef = useRef<string | null>(null);
  useEffect(() => {
    if (!current || !isSingleRun) return;
    if (lastPhaseRef.current !== "finished" && current.phase === "finished") {
      qc.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
      qc.invalidateQueries({ queryKey: ["run-stocks", current.id] });
    }
    lastPhaseRef.current = current.phase;
  }, [current, isSingleRun, qc]);

  if (kickoff?.status === "already_running" && current && current.stocks_total > 1) {
    return (
      <div className="refresh-status-card refresh-status-warn" role="status">
        <strong>Ein Marktdaten-Update für die gesamte Watchlist läuft bereits.</strong>
        <span>
          {" "}
          Fortschritt unter{" "}
          <Link to="/runs" className="refresh-status-link">
            Laufstatus
          </Link>
          .
        </span>
      </div>
    );
  }

  if (!current || !isSingleRun || !myStock) {
    return null;
  }

  const succeeded = current.phase === "finished" && myStock.overall_status === "done";
  const failed = current.phase === "finished" && myStock.overall_status !== "done";
  const stepError =
    myStock.symbol.error || myStock.quote.error || myStock.metrics.error || null;

  const headerLabel = isRunning
    ? "Marktdaten werden aktualisiert"
    : succeeded
    ? "Marktdaten aktualisiert"
    : "Marktdaten-Update fehlgeschlagen";

  const subLabel = isRunning
    ? `Run #${current.id} · ${phaseLabel(current.phase)} · ${formatDuration(liveRunSeconds(current), { dashOnZero: false })}`
    : `Run #${current.id} · Fertig um ${formatTimeShort(current.finished_at)} · ${formatDuration(liveRunSeconds(current), { dashOnZero: false })}`;

  return (
    <section
      className={`refresh-status-card ${
        succeeded ? "refresh-status-ok" : failed ? "refresh-status-err" : "refresh-status-running"
      }`}
      aria-live="polite"
    >
      <div className="refresh-status-head">
        <div>
          <div className="refresh-status-title">{headerLabel}</div>
          <div className="refresh-status-sub">{subLabel}</div>
        </div>
        {myStock.resolved_symbol && (
          <span className="refresh-status-symbol" title="Ermitteltes Symbol">
            {myStock.resolved_symbol}
          </span>
        )}
      </div>
      <div className="refresh-step-grid">
        <StepRow
          label="Symbol"
          status={myStock.symbol.status as StepStatus}
          error={myStock.symbol.error}
        />
        <StepRow
          label="Kurs"
          status={myStock.quote.status as StepStatus}
          error={myStock.quote.error}
        />
        <StepRow
          label="Kennzahlen"
          status={myStock.metrics.status as StepStatus}
          error={myStock.metrics.error}
        />
      </div>
      {failed && stepError && (
        <p className="refresh-status-banner refresh-status-banner-err" role="alert">
          {stepError}
        </p>
      )}
    </section>
  );
}

export function StockDetailPage() {
  const { isin } = useParams<{ isin: string }>();
  const navigate = useNavigate();
  const stockQuery = useStock(isin);
  const refreshMutation = useRefreshStock();
  const deleteMutation = useDeleteStock();
  const stock = stockQuery.data;
  const refreshKickoff = refreshMutation.data ?? null;
  useDocumentTitle(stock?.name ?? null);

  const { data: currentRun } = useCurrentRun();
  const isRefreshInFlight =
    refreshMutation.isPending ||
    (currentRun != null && currentRun.phase !== "finished");
  const isBulkRunActive =
    currentRun != null &&
    currentRun.phase !== "finished" &&
    currentRun.stocks_total > 1;

  if (!isin) {
    return (
      <div className="page">
        <p>Keine ISIN angegeben.</p>
        <Link to="/watchlist" className="btn-secondary">Zurück zur Watchlist</Link>
      </div>
    );
  }

  if (stockQuery.isLoading && !stock) {
    return (
      <div className="page">
        <Spinner label="Lade Detailansicht..." />
      </div>
    );
  }

  if (stockQuery.isError || !stock) {
    return (
      <div className="page">
        <p className="form-banner-error">
          {extractApiError(stockQuery.error, "Unternehmen konnte nicht geladen werden.")}
        </p>
        <Link to="/watchlist" className="btn-secondary">Zurück zur Watchlist</Link>
      </div>
    );
  }

  async function handleRefresh() {
    try {
      await refreshMutation.mutateAsync(isin!);
    } catch (err) {
      toast.error(extractApiError(err, "Aktualisierung konnte nicht gestartet werden."));
    }
  }

  async function handleDelete() {
    if (!stock) return;
    const ok = await confirm({
      title: "Unternehmen löschen",
      message: `Unternehmen ${stock.name} (${stock.isin}) wirklich löschen?`,
      destructive: true,
      confirmLabel: "Löschen",
    });
    if (!ok) return;
    try {
      await deleteMutation.mutateAsync(isin!);
      toast.success(`${stock.name} gelöscht.`);
      navigate("/watchlist");
    } catch (err) {
      toast.error(extractApiError(err, "Löschen fehlgeschlagen."));
    }
  }

  return (
    <div className="page detail-page">
      <header className="detail-breadcrumb">
        <Link to="/watchlist" className="breadcrumb-link">Watchlist</Link>
        <span className="breadcrumb-sep">›</span>
        <span className="breadcrumb-current">{stock.name}</span>
      </header>

      <section className="detail-hero">
        <div className="detail-hero-main">
          <div className="detail-hero-title-row">
            <h2>{stock.name}</h2>
            <span className="isin-pill" title="ISIN">{stock.isin}</span>
            {stock.burggraben && (
              <span className="badge detail-burggraben-badge" title="Burggraben">
                Burggraben
              </span>
            )}
          </div>
          <div className="detail-hero-meta">
            {stock.sector && <span className="detail-sector">{stock.sector}</span>}
            {stock.tags && stock.tags.length > 0 && (
              <span className="tag-list">
                {stock.tags.map((t) => (
                  <span key={t} className={`tag-pill tag-pill-sm ${tagColorClass(t)}`}>{t}</span>
                ))}
              </span>
            )}
          </div>
          <div className="detail-hero-links">
            {stock.link_yahoo && (
              <a href={stock.link_yahoo} target="_blank" rel="noreferrer" className="detail-link">
                Yahoo Finance ↗
              </a>
            )}
            {stock.link_finanzen && (
              <a href={stock.link_finanzen} target="_blank" rel="noreferrer" className="detail-link">
                Finanzen.net ↗
              </a>
            )}
            {stock.link_onvista_chart && (
              <a href={stock.link_onvista_chart} target="_blank" rel="noreferrer" className="detail-link">
                Onvista Chart ↗
              </a>
            )}
            {stock.link_onvista_fundamental && (
              <a href={stock.link_onvista_fundamental} target="_blank" rel="noreferrer" className="detail-link">
                Onvista Fundamentals ↗
              </a>
            )}
            <a
              href={`https://www.comdirect.de/inf/aktien/${stock.isin}`}
              target="_blank"
              rel="noreferrer"
              className="detail-link"
            >
              comdirect ↗
            </a>
          </div>
        </div>
        <div className="detail-hero-side">
          <div className="detail-price-block">
            <div className="detail-price-value">{formatCurrency(stock.current_price, stock.currency)}</div>
            <div className={`detail-price-change ${changeClass(stock.day_change_pct, defaultThresholds)}`}>
              {formatPercent(stock.day_change_pct)} heute
            </div>
            <div className="detail-price-meta">Stand: {formatDate(stock.last_updated)}</div>
          </div>
        </div>
        <div className="detail-hero-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={handleRefresh}
            disabled={isRefreshInFlight}
            title={
              isBulkRunActive
                ? "Ein Marktdaten-Update für die gesamte Watchlist läuft bereits"
                : isRefreshInFlight
                ? "Aktualisierung läuft bereits"
                : "Marktdaten neu laden"
            }
          >
            {isRefreshInFlight ? "Läuft…" : "Marktdaten aktualisieren"}
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => navigate(`/stocks/${stock.isin}/edit`)}
          >
            Bearbeiten
          </button>
        </div>
      </section>

      <RefreshStatusCard isin={isin} kickoff={refreshKickoff} />

      <section className="detail-grid">
        <HistoryChart isin={isin} stock={stock} />

        <div className="detail-card">
          <div className="detail-card-head">
            <h3>Kennzahlen</h3>
            <span className="detail-card-hint">
              {stock.missing_metrics.length > 0
                ? `${stock.missing_metrics.length} Kennzahl${stock.missing_metrics.length === 1 ? "" : "en"} fehlen`
                : "Vollständig"}
            </span>
          </div>
          <div className="run-summary-grid">
            <KpiTile
              label="Kurs/Gewinn (fwd)"
              value={formatNumber(stock.pe_forward, 2)}
              sub={
                stock.pe_min_5y != null && stock.pe_max_5y != null
                  ? `5J-Band: ${formatNumber(stock.pe_min_5y, 1)}–${formatNumber(stock.pe_max_5y, 1)}`
                  : undefined
              }
            />
            <KpiTile
              label="Dividende"
              value={formatPercent(stock.dividend_yield_current, 2, { showSign: false })}
              sub={
                stock.dividend_yield_avg_5y != null
                  ? `Ø 5J: ${formatPercent(stock.dividend_yield_avg_5y, 2, { showSign: false })}`
                  : undefined
              }
              className={dividendClass(stock.dividend_yield_current, defaultThresholds) ? "kpi-highlight" : ""}
            />
            <KpiTile
              label="Marktkapitalisierung"
              value={formatLargeCurrency(stock.market_cap, stock.currency)}
            />
            <KpiTile
              label="Eigenkapitalquote"
              value={formatPercent(stock.equity_ratio, 2, { showSign: false })}
              className={equityRatioClass(stock.equity_ratio, defaultThresholds)}
            />
            <KpiTile
              label="Verschuldungsgrad"
              value={formatPercent(stock.debt_ratio)}
            />
            <KpiTile
              label="Umsatzwachstum"
              value={formatPercent(stock.revenue_growth)}
            />
            <KpiTile
              label="Analystenziel (1J)"
              value={formatCurrency(stock.analyst_target_1y, stock.currency)}
              sub={
                stock.analyst_target_distance_pct != null
                  ? `Distanz: ${formatPercent(stock.analyst_target_distance_pct)}`
                  : undefined
              }
              className={
                targetClass(stock.analyst_target_distance_pct, defaultThresholds) ? "kpi-highlight" : ""
              }
            />
            <KpiTile
              label="Tranchen"
              value={String(stock.tranches)}
              sub={`${formatCurrency(stock.invested_capital_eur, "EUR")} investiert`}
            />
          </div>
        </div>
      </section>

      <Suspense fallback={<Spinner label="Lade KI-Analysen…" />}>
        <AIAgentsPanel isin={isin} />
      </Suspense>

      <section className="detail-card">
        <div className="detail-card-head">
          <h3>Eigene Notizen</h3>
          <Link to={`/stocks/${isin}/edit`} className="detail-card-hint detail-card-hint-link">
            {stock.reasoning ? "Notiz bearbeiten" : "Notiz hinzufügen"}
          </Link>
        </div>
        {stock.reasoning ? (
          <p className="detail-ai-text">{stock.reasoning}</p>
        ) : (
          <EmptyState
            variant="inline"
            title="Noch keine Notizen"
            description="Halte hier deine Investment-These, Beobachtungen oder offene Fragen fest – nur für dich."
            action={
              <Link to={`/stocks/${isin}/edit`} className="btn-secondary">
                Notiz hinzufügen
              </Link>
            }
          />
        )}
      </section>

      <PeersStrip isin={isin} />

      <section className="detail-card detail-audit-card">
        <div className="detail-card-head">
          <h3>Audit & Datenquellen</h3>
        </div>
        <div className="detail-audit-grid">
          <div>
            <div className="detail-audit-label">Resolved Symbol</div>
            <div className="detail-audit-value">{stock.ticker_override || "–"}</div>
          </div>
          <div>
            <div className="detail-audit-label">Letzter Marktdaten-Refresh</div>
            <div className="detail-audit-value">{formatDate(stock.last_updated)}</div>
          </div>
          <div>
            <div className="detail-audit-label">Status</div>
            <div className="detail-audit-value">{stock.last_status ?? "–"}</div>
          </div>
        </div>
        <div className="detail-danger-zone">
          <div>
            <strong>Unternehmen löschen</strong>
            <p>Entfernt das Unternehmen samt Marktdaten und Historie. Nicht umkehrbar.</p>
          </div>
          <button
            type="button"
            className="btn-danger"
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
          >
            {deleteMutation.isPending ? "Lösche…" : "Löschen"}
          </button>
        </div>
      </section>
    </div>
  );
}

export default StockDetailPage;
