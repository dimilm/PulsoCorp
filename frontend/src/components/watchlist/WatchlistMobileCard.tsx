import { Link } from "react-router-dom";

import { type JobsAggregate } from "../WatchlistTable";
import { JobsSparkline } from "../jobs/JobsSparkline";
import RowActionsMenu from "../RowActionsMenu";
import { AIPillRow } from "../ai/AIPillRow";
import {
  changeClass,
  type ColorThresholds,
  defaultThresholds,
  targetClass,
} from "../../lib/colorRules";
import { formatNumber, formatPercent } from "../../lib/format";
import { tagColorClass } from "../../lib/tagColor";
import type { JobsTrendPoint } from "../../hooks/useJobsTrendsAggregate";
import type { Stock } from "../../types";

const MAX_VISIBLE_TAGS = 2;

interface Props {
  stock: Stock;
  thresholds?: ColorThresholds;
  onRefresh: (isin: string) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
  refreshDisabled?: boolean;
  jobsAggregate?: JobsAggregate;
  trendPoints?: JobsTrendPoint[];
}

function formatJobsDelta(delta: number | null | undefined): string {
  if (delta == null) return "";
  if (delta === 0) return "±0";
  return delta > 0 ? `+${delta}` : `${delta}`;
}

export function WatchlistMobileCard({
  stock,
  thresholds = defaultThresholds,
  onRefresh,
  onEdit,
  onDelete,
  refreshDisabled = false,
  jobsAggregate,
  trendPoints,
}: Props) {
  const hasSparkline = trendPoints && trendPoints.length >= 2;
  const hasDelta = jobsAggregate?.delta_7d != null && jobsAggregate.delta_7d !== 0;

  return (
    <div className="wl-card">
      {/* Header row: name + actions */}
      <div className="wl-card-header">
        <div className="wl-card-name-block">
          <Link
            to={`/stocks/${stock.isin}`}
            className="wl-card-name"
          >
            {stock.name}
          </Link>
          <div className="wl-card-meta">
            <span className="wl-card-isin">{stock.isin}</span>
            {stock.sector && (
              <>
                <span className="wl-card-meta-sep" aria-hidden="true">·</span>
                <span className="wl-card-sector">{stock.sector}</span>
              </>
            )}
          </div>
        </div>
        <RowActionsMenu
          stock={stock}
          onRefresh={onRefresh}
          onEdit={onEdit}
          onDelete={onDelete}
          refreshDisabled={refreshDisabled}
        />
      </div>

      {/* KPI row: Kurs · Tagesänderung · Kursziel */}
      <div className="wl-card-kpis">
        <div className="wl-card-kpi">
          <span className="wl-card-kpi-label">Kurs</span>
          <span className="wl-card-kpi-value">
            {formatNumber(stock.current_price) ?? "–"}
          </span>
        </div>
        <div className="wl-card-kpi">
          <span className="wl-card-kpi-label">Tagesänd.</span>
          <span className={`wl-card-kpi-value ${changeClass(stock.day_change_pct, thresholds)}`}>
            {formatPercent(stock.day_change_pct, 2, { withUnit: false }) ?? "–"}
          </span>
        </div>
        <div className="wl-card-kpi">
          <span className="wl-card-kpi-label">Kursziel</span>
          <span className={`wl-card-kpi-value ${targetClass(stock.analyst_target_distance_pct, thresholds)}`}>
            {formatPercent(stock.analyst_target_distance_pct, 2, { withUnit: false }) ?? "–"}
          </span>
        </div>
      </div>

      {/* Stellen row — prominence per user request */}
      {jobsAggregate?.latest != null && (
        <div className="wl-card-jobs">
          <span className="wl-card-jobs-label">Offene Stellen</span>
          <div className="wl-card-jobs-row">
            <span className="wl-card-jobs-count">{jobsAggregate.latest}</span>
            {hasDelta && (
              <span
                className={`wl-card-jobs-delta ${jobsAggregate.delta_7d! > 0 ? "delta-up" : "delta-down"}`}
              >
                {formatJobsDelta(jobsAggregate.delta_7d)} (7T)
              </span>
            )}
            {hasSparkline && (
              <JobsSparkline points={trendPoints} width={120} height={32} />
            )}
          </div>
        </div>
      )}

      {/* Footer: status badge + tags */}
      <div className="wl-card-footer">
        <div className="wl-card-left">
          {stock.last_status && (
            <span className="wl-card-status">{stock.last_status}</span>
          )}
          <AIPillRow stock={stock} />
        </div>
        {stock.tags && stock.tags.length > 0 && (
          <span className="tag-list">
            {stock.tags.slice(0, MAX_VISIBLE_TAGS).map((t) => (
              <span key={t} className={`tag-pill tag-pill-sm ${tagColorClass(t)}`}>
                {t}
              </span>
            ))}
            {stock.tags.length > MAX_VISIBLE_TAGS && (
              <span
                className="tag-pill tag-pill-sm tag-pill-overflow"
                title={stock.tags.slice(MAX_VISIBLE_TAGS).join(", ")}
              >
                +{stock.tags.length - MAX_VISIBLE_TAGS}
              </span>
            )}
          </span>
        )}
      </div>
    </div>
  );
}
