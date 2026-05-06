import { Link } from "react-router-dom";

import { Stock } from "../types";
import {
  changeClass,
  ColorThresholds,
  defaultThresholds,
  dividendClass,
  targetClass,
} from "../lib/colorRules";
import { formatNumber, formatPercent } from "../lib/format";
import { tagColorClass } from "../lib/tagColor";
import { AIPillRow } from "./ai/AIPillRow";
import { JobsSparkline } from "./jobs/JobsSparkline";
import RowActionsMenu from "./RowActionsMenu";
import type { JobsTrendPoint } from "../hooks/useJobsTrendsAggregate";

const MAX_VISIBLE_TAGS = 3;

export interface JobsAggregate {
  latest: number | null;
  delta_7d: number | null;
}

interface Props {
  stocks: Stock[];
  sortBy: string;
  sortDir: "asc" | "desc";
  thresholds?: ColorThresholds;
  onSort: (key: string) => void;
  onRefresh: (isin: string) => Promise<void>;
  onEdit: (stock: Stock) => void;
  onDelete: (stock: Stock) => Promise<void>;
  refreshDisabled?: boolean;
  // Per-ISIN aggregated job counts (latest + Δ7T). Optional because the
  // data may not have loaded yet — cells fall back to "-" until present.
  jobsByIsin?: Record<string, JobsAggregate>;
  // Per-ISIN 90-day trend timeseries powering the sparkline. Optional for
  // the same reason; cells render the count without a chart when fewer
  // than 2 points are available.
  trendsByIsin?: Record<string, JobsTrendPoint[]>;
}

function formatJobsDelta(delta: number | null | undefined): string {
  if (delta == null) return "";
  if (delta === 0) return " (0)";
  return delta > 0 ? ` (+${delta})` : ` (${delta})`;
}

function buildJobsCellTitle(
  latest: number | null,
  delta7d: number | null,
  points: JobsTrendPoint[] | undefined
): string {
  const parts: string[] = [];
  parts.push(`Aktuell: ${latest != null ? latest : "–"}`);
  if (delta7d != null) {
    const sign = delta7d > 0 ? `+${delta7d}` : `${delta7d}`;
    parts.push(`Δ 7T: ${sign}`);
  }
  if (points && points.length >= 2) {
    let min = points[0].count;
    let max = points[0].count;
    for (const p of points) {
      if (p.count < min) min = p.count;
      if (p.count > max) max = p.count;
    }
    parts.push(`90T min/max: ${min}/${max}`);
  }
  return parts.join(" · ");
}

function SortHeader({
  label,
  keyName,
  sortBy,
  sortDir,
  onSort,
  className,
}: {
  label: string;
  keyName: string;
  sortBy: string;
  sortDir: "asc" | "desc";
  onSort: (key: string) => void;
  className?: string;
}) {
  const marker = sortBy === keyName ? (sortDir === "asc" ? " ▲" : " ▼") : "";
  return (
    <th className={className}>
      <button type="button" onClick={() => onSort(keyName)}>
        {label}
        {marker}
      </button>
    </th>
  );
}

export default function WatchlistTable({
  stocks,
  sortBy,
  sortDir,
  thresholds = defaultThresholds,
  onSort,
  onRefresh,
  onEdit,
  onDelete,
  refreshDisabled = false,
  jobsByIsin,
  trendsByIsin,
}: Props) {
  return (
    <div className="table-scroll">
    <table className="watchlist-table">
      <thead>
        <tr>
          <SortHeader label="ISIN" keyName="isin" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Name" keyName="name" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <SortHeader label="Sektor" keyName="sector" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <th>Tags</th>
          <SortHeader label="Tranchen" keyName="tranches" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="num-cell" />
          <SortHeader label="Kurs" keyName="current_price" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="num-cell" />
          <SortHeader label="Tagesänd. (%)" keyName="day_change_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="num-cell" />
          <SortHeader label="Kursziel (%)" keyName="analyst_target_distance_pct" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="num-cell" />
          <SortHeader label="Div. (%)" keyName="dividend_yield_current" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="num-cell" />
          <th className="num-cell" title="Aktuell offene Stellen · 90-Tage-Trend">
            Stellen
          </th>
          <SortHeader label="Status" keyName="last_status" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
          <th>KI</th>
          <th className="actions-header" aria-label="Aktionen" />
        </tr>
      </thead>
      <tbody>
        {stocks.map((s) => (
          <tr key={s.isin}>
            <td>{s.isin}</td>
            <td>
              <Link to={`/stocks/${s.isin}`} className="stock-name-link">
                {s.name}
              </Link>
            </td>
            <td>{s.sector ?? "-"}</td>
            <td>
              {s.tags && s.tags.length > 0 ? (
                <span className="tag-list">
                  {s.tags.slice(0, MAX_VISIBLE_TAGS).map((t) => (
                    <span key={t} className={`tag-pill tag-pill-sm ${tagColorClass(t)}`}>
                      {t}
                    </span>
                  ))}
                  {s.tags.length > MAX_VISIBLE_TAGS && (
                    <span
                      className="tag-pill tag-pill-sm tag-pill-overflow"
                      title={s.tags.slice(MAX_VISIBLE_TAGS).join(", ")}
                    >
                      +{s.tags.length - MAX_VISIBLE_TAGS}
                    </span>
                  )}
                </span>
              ) : (
                "-"
              )}
            </td>
            <td className="num-cell">{s.tranches}</td>
            <td className="num-cell">{formatNumber(s.current_price)}</td>
            <td className="num-cell">
              <span className={changeClass(s.day_change_pct, thresholds)}>
                {formatPercent(s.day_change_pct, 2, { withUnit: false })}
              </span>
            </td>
            <td className="num-cell">
              <span className={targetClass(s.analyst_target_distance_pct, thresholds)}>
                {formatPercent(s.analyst_target_distance_pct, 2, { withUnit: false })}
              </span>
            </td>
            <td className="num-cell">
              <span className={dividendClass(s.dividend_yield_current, thresholds)}>
                {formatPercent(s.dividend_yield_current, 2, { withUnit: false, showSign: false })}
              </span>
            </td>
            <td className="num-cell">
              {(() => {
                const aggregate = jobsByIsin?.[s.isin];
                if (!aggregate || aggregate.latest == null) return "-";
                const trendPoints = trendsByIsin?.[s.isin];
                const hasSparkline = trendPoints && trendPoints.length >= 2;
                const title = buildJobsCellTitle(
                  aggregate.latest,
                  aggregate.delta_7d,
                  trendPoints
                );
                return (
                  <span className="jobs-sparkline-cell" title={title}>
                    {hasSparkline ? (
                      <JobsSparkline points={trendPoints} />
                    ) : null}
                    <span className="jobs-sparkline-cell-value">
                      {aggregate.latest}
                      {aggregate.delta_7d != null && aggregate.delta_7d !== 0 ? (
                        <span
                          className={
                            aggregate.delta_7d > 0 ? "delta-up" : "delta-down"
                          }
                        >
                          {formatJobsDelta(aggregate.delta_7d)}
                        </span>
                      ) : null}
                    </span>
                  </span>
                );
              })()}
            </td>
            <td>{s.last_status ?? "-"}</td>
            <td className="ai-pills-cell">
              <AIPillRow stock={s} />
            </td>
            <td className="actions-cell">
              <RowActionsMenu
                stock={s}
                onRefresh={onRefresh}
                onEdit={onEdit}
                onDelete={onDelete}
                refreshDisabled={refreshDisabled}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
