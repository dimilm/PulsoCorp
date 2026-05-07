import { Link } from "react-router-dom";

import { formatDateOnly } from "../../lib/format";
import { STEP_STATUS_LABEL } from "../../lib/runProgress";
import type { JobSource, RunJobStatus } from "../../types/jobs";
import type { StepStatus } from "../../types/run";

interface Props {
  sources: JobSource[];
  statusByJobId: Map<number, RunJobStatus>;
  isRunning: boolean;
  onRefreshSource: (source: JobSource) => void;
  isRefreshPending: boolean;
}

function formatDelta(delta: number | null | undefined): string {
  if (delta == null) return "–";
  if (delta === 0) return "0";
  return delta > 0 ? `+${delta}` : `${delta}`;
}

function deltaClass(delta: number | null | undefined): string {
  if (delta == null || delta === 0) return "";
  return delta > 0 ? "delta-up" : "delta-down";
}

export function JobsMobileList({
  sources,
  statusByJobId,
  isRunning,
  onRefreshSource,
  isRefreshPending,
}: Props) {
  if (sources.length === 0) {
    return <p className="run-empty">Keine Quellen gefunden.</p>;
  }

  return (
    <div className="jobs-mobile-list">
      {sources.map((source) => {
        const status = statusByJobId.get(source.id);
        const liveStatus = (
          status?.overall_status ??
          (isRunning ? "not_started" : null)
        ) as StepStatus | null;
        const isRowRunning = liveStatus === "running";
        const otherRowRunning = isRunning && !isRowRunning;

        return (
          <div
            key={source.id}
            className={`jobs-mobile-card${liveStatus ? ` run-row-${liveStatus}` : ""}`}
          >
            {/* Header */}
            <div className="jobs-mobile-card-header">
              <div className="jobs-mobile-card-name-block">
                <Link to={`/jobs/${source.id}`} className="jobs-mobile-card-name">
                  {source.name}
                </Link>
                <div className="jobs-mobile-card-meta">
                  <code className="jobs-mobile-card-adapter">{source.adapter_type}</code>
                  {source.isin && (
                    <>
                      <span className="jobs-mobile-card-sep" aria-hidden="true">·</span>
                      <Link to={`/stocks/${source.isin}`} className="breadcrumb-link" style={{ fontSize: 11 }}>
                        {source.isin}
                      </Link>
                    </>
                  )}
                  <span className={`badge${source.is_active ? " run-badge-done" : " badge-muted"}`} style={{ fontSize: 10 }}>
                    {source.is_active ? "aktiv" : "inaktiv"}
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => onRefreshSource(source)}
                disabled={isRefreshPending || otherRowRunning || isRowRunning}
                title={
                  isRowRunning ? "Wird gerade aktualisiert"
                  : otherRowRunning ? "Ein Lauf läuft bereits"
                  : "Einzeln aktualisieren"
                }
              >
                {isRowRunning ? "Läuft…" : "Refresh"}
              </button>
            </div>

            {/* KPI row */}
            <div className="jobs-mobile-card-kpis">
              <div className="jobs-mobile-card-kpi">
                <span className="jobs-mobile-card-kpi-label">Aktuell</span>
                <span className="jobs-mobile-card-kpi-value jobs-mobile-card-count">
                  {source.latest_count != null ? source.latest_count : "–"}
                </span>
              </div>
              <div className="jobs-mobile-card-kpi">
                <span className="jobs-mobile-card-kpi-label">Δ 7T</span>
                <span className={`jobs-mobile-card-kpi-value ${deltaClass(source.delta_7d)}`}>
                  {formatDelta(source.delta_7d)}
                </span>
              </div>
              <div className="jobs-mobile-card-kpi">
                <span className="jobs-mobile-card-kpi-label">Δ 30T</span>
                <span className={`jobs-mobile-card-kpi-value ${deltaClass(source.delta_30d)}`}>
                  {formatDelta(source.delta_30d)}
                </span>
              </div>
              <div className="jobs-mobile-card-kpi">
                <span className="jobs-mobile-card-kpi-label">Stand</span>
                <span className="jobs-mobile-card-kpi-value" style={{ fontSize: 12 }}>
                  {formatDateOnly(source.latest_snapshot_date)}
                </span>
              </div>
            </div>

            {/* Live status */}
            {liveStatus && (
              <div className="jobs-mobile-card-status">
                <span className={`run-badge run-badge-${liveStatus}`}>
                  {STEP_STATUS_LABEL[liveStatus]}
                </span>
                {status?.error && (
                  <span className="run-step-error" style={{ fontSize: 11 }}>{status.error}</span>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default JobsMobileList;
