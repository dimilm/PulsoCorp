import { useNavigate } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useChartTheme } from "../../hooks/useChartTheme";
import {
  useJobSourceTrend,
  useRefreshJobSource,
  useStockJobs,
} from "../../hooks/useJobSources";
import { StockJobsTrendChart } from "./StockJobsTrendChart";
import { extractApiError } from "../../lib/apiError";
import { formatDateOnly } from "../../lib/format";
import { toast } from "../../lib/toast";
import type { JobSource } from "../../types/jobs";
import { EmptyState } from "../EmptyState";
import { Spinner } from "../Spinner";

interface StockJobsCardProps {
  isin: string;
}

function deltaClass(delta: number | null | undefined): string {
  if (delta == null || delta === 0) return "";
  return delta > 0 ? "delta-up" : "delta-down";
}

function formatDelta(delta: number | null | undefined): string {
  if (delta == null) return "–";
  if (delta === 0) return "0";
  return delta > 0 ? `+${delta}` : `${delta}`;
}

export function StockJobsCard({ isin }: StockJobsCardProps) {
  const navigate = useNavigate();
  const query = useStockJobs(isin);
  const refreshMutation = useRefreshJobSource();

  if (query.isLoading) {
    return (
      <section className="detail-card">
        <div className="detail-card-head">
          <h3>Offene Stellen</h3>
        </div>
        <Spinner label="Lade Jobdaten…" />
      </section>
    );
  }

  if (query.isError || !query.data) {
    return (
      <section className="detail-card">
        <div className="detail-card-head">
          <h3>Offene Stellen</h3>
        </div>
        <p className="form-banner-error">
          {extractApiError(query.error, "Jobdaten konnten nicht geladen werden.")}
        </p>
      </section>
    );
  }

  const { sources, total_latest, total_delta_7d, total_delta_30d } = query.data;

  if (sources.length === 0) {
    return (
      <section className="detail-card">
        <div className="detail-card-head">
          <h3>Offene Stellen</h3>
          <button
            type="button"
            className="detail-card-hint detail-card-hint-link"
            onClick={() => navigate(`/jobs/new?isin=${isin}`)}
          >
            Quelle hinzufügen
          </button>
        </div>
        <EmptyState
          variant="inline"
          title="Keine Karriereportal-Quelle konfiguriert"
          description="Lege eine Quelle an, um die Anzahl offener Stellen zu beobachten."
          action={
            <button
              type="button"
              className="btn-secondary"
              onClick={() => navigate(`/jobs/new?isin=${isin}`)}
            >
              Quelle hinzufügen
            </button>
          }
        />
      </section>
    );
  }

  async function handleRefresh(source: JobSource) {
    try {
      const result = await refreshMutation.mutateAsync(source.id);
      if (result.status === "started") {
        toast.success(`Aktualisierung für ${source.name} gestartet.`);
      } else if (result.status === "already_running") {
        toast.info("Eine andere Job-Aktualisierung läuft bereits.");
      } else {
        toast.info(`Status: ${result.status}`);
      }
    } catch (err) {
      toast.error(extractApiError(err, "Aktualisierung konnte nicht gestartet werden."));
    }
  }

  return (
    <section className="detail-card">
      <div className="detail-card-head">
        <h3>Offene Stellen</h3>
        <button
          type="button"
          className="detail-card-hint detail-card-hint-link"
          onClick={() => navigate(`/jobs?isin=${isin}`)}
        >
          Alle Quellen verwalten
        </button>
      </div>

      <StockJobsTrendChart isin={isin} />

      <div className="run-summary-grid">
        <div className="run-summary-item">
          <div className="run-summary-label">Aktuell offen (gesamt)</div>
          <div className="run-summary-value">
            {total_latest != null ? total_latest : "–"}
          </div>
          <div className="run-summary-sub">
            {sources.length === 1 ? "1 Quelle" : `${sources.length} Quellen`}
          </div>
        </div>
        <div className="run-summary-item">
          <div className="run-summary-label">Δ 7 Tage</div>
          <div className={`run-summary-value ${deltaClass(total_delta_7d)}`}>
            {formatDelta(total_delta_7d)}
          </div>
        </div>
        <div className="run-summary-item">
          <div className="run-summary-label">Δ 30 Tage</div>
          <div className={`run-summary-value ${deltaClass(total_delta_30d)}`}>
            {formatDelta(total_delta_30d)}
          </div>
        </div>
      </div>

      <div className="job-source-list">
        {sources.map((source) => (
          <JobSourceRow
            key={source.id}
            source={source}
            onRefresh={() => handleRefresh(source)}
            refreshing={refreshMutation.isPending}
          />
        ))}
      </div>
    </section>
  );
}

interface JobSourceRowProps {
  source: JobSource;
  onRefresh: () => void;
  refreshing: boolean;
}

function JobSourceRow({ source, onRefresh, refreshing }: JobSourceRowProps) {
  const navigate = useNavigate();
  const trendQuery = useJobSourceTrend(source.id, 90);
  const chartTheme = useChartTheme();
  const points = (trendQuery.data?.points ?? []).map((p) => ({
    date: p.snapshot_date,
    count: p.jobs_count,
  }));

  return (
    <div className="job-source-row">
      <div className="job-source-row-head">
        <div>
          <div className="job-source-name">
            <a
              href={source.portal_url}
              target="_blank"
              rel="noreferrer"
              className="detail-link"
            >
              {source.name} ↗
            </a>
            {!source.is_active && <span className="badge badge-muted">inaktiv</span>}
          </div>
          <div className="job-source-meta">
            <span>{source.adapter_type}</span>
            {source.latest_snapshot_date && (
              <span> · zuletzt: {formatDateOnly(source.latest_snapshot_date)}</span>
            )}
          </div>
        </div>
        <div className="job-source-stats">
          <div className="job-source-stat">
            <div className="job-source-stat-label">Aktuell</div>
            <div className="job-source-stat-value">
              {source.latest_count != null ? source.latest_count : "–"}
            </div>
          </div>
          <div className="job-source-stat">
            <div className="job-source-stat-label">Δ 7T</div>
            <div className={`job-source-stat-value ${deltaClass(source.delta_7d)}`}>
              {formatDelta(source.delta_7d)}
            </div>
          </div>
          <div className="job-source-stat">
            <div className="job-source-stat-label">Δ 30T</div>
            <div className={`job-source-stat-value ${deltaClass(source.delta_30d)}`}>
              {formatDelta(source.delta_30d)}
            </div>
          </div>
          <div className="job-source-actions">
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={onRefresh}
              disabled={refreshing}
            >
              {refreshing ? "Läuft…" : "Aktualisieren"}
            </button>
            <button
              type="button"
              className="btn-ghost btn-sm"
              onClick={() => navigate(`/jobs/${source.id}`)}
            >
              Bearbeiten
            </button>
          </div>
        </div>
      </div>
      {points.length >= 2 && (
        <div className="job-source-chart">
          <ResponsiveContainer width="100%" height={80}>
            <LineChart data={points} margin={{ left: 8, right: 8, top: 8, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                stroke={chartTheme.tick}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                stroke={chartTheme.tick}
                tick={{ fontSize: 10 }}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  background: chartTheme.tooltipBackground,
                  borderColor: chartTheme.tooltipBorder,
                  color: chartTheme.tooltipText,
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: chartTheme.tooltipText }}
                formatter={(value) => [`${value ?? "–"}`, "Stellen"]}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke={chartTheme.line}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default StockJobsCard;
