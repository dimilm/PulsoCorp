import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
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
import { useStockJobsTrend } from "../../hooks/useJobSources";
import { formatDateOnly } from "../../lib/format";
import { Spinner } from "../Spinner";
import type { HistoryRange } from "../../types";

const RANGE_LABELS: { key: HistoryRange; label: string }[] = [
  { key: "1m", label: "1M" },
  { key: "6m", label: "6M" },
  { key: "1y", label: "1J" },
  { key: "5y", label: "5J" },
  { key: "max", label: "Max" },
];

const RANGE_TO_DAYS: Record<HistoryRange, number> = {
  "1m": 30,
  "6m": 180,
  "1y": 365,
  "5y": 1825,
  max: 3650,
};

const VALID_RANGES = new Set<HistoryRange>(["1m", "6m", "1y", "5y", "max"]);
const DEFAULT_RANGE: HistoryRange = "6m";
const SEARCH_PARAM = "jobs_range";

function parseRangeParam(value: string | null): HistoryRange {
  if (value && VALID_RANGES.has(value as HistoryRange)) {
    return value as HistoryRange;
  }
  return DEFAULT_RANGE;
}

function tickFormatter(value: string, range: HistoryRange): string {
  const d = new Date(value);
  if (range === "1m" || range === "6m")
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  if (range === "1y" || range === "5y")
    return d.toLocaleDateString("de-DE", { month: "short", year: "2-digit" });
  return d.toLocaleDateString("de-DE", { year: "numeric" });
}

interface StockJobsTrendChartProps {
  isin: string;
}

export function StockJobsTrendChart({ isin }: StockJobsTrendChartProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const range = parseRangeParam(searchParams.get(SEARCH_PARAM));
  const days = RANGE_TO_DAYS[range];
  const chartTheme = useChartTheme();

  const setRange = (next: HistoryRange) => {
    const params = new URLSearchParams(searchParams);
    if (next === DEFAULT_RANGE) {
      params.delete(SEARCH_PARAM);
    } else {
      params.set(SEARCH_PARAM, next);
    }
    setSearchParams(params, { replace: true });
  };

  const query = useStockJobsTrend(isin, days);
  const points = query.data?.points ?? [];

  const chartData = useMemo(
    () => points.map((p) => ({ date: p.snapshot_date, count: p.jobs_count })),
    [points]
  );

  const yMax = useMemo(() => {
    if (chartData.length === 0) return "auto";
    const max = Math.max(...chartData.map((p) => p.count));
    return Math.ceil(max * 1.05) || 10;
  }, [chartData]);

  return (
    <div className="jobs-trend-chart">
      <div className="detail-chart-header">
        <span className="jobs-trend-chart-label">Stellen-Verlauf</span>
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

      {query.isLoading && <Spinner label="Lade Stellen-Verlauf…" />}

      {!query.isLoading && chartData.length < 2 && (
        <div className="detail-chart-empty">
          Noch nicht genug Datenpunkte für diesen Zeitraum vorhanden.
        </div>
      )}

      {chartData.length >= 2 && (
        <div className="detail-chart-body">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(v: string) => tickFormatter(v, range)}
                minTickGap={32}
                tick={{ fontSize: 11, fill: chartTheme.tick }}
                stroke={chartTheme.grid}
              />
              <YAxis
                domain={[0, yMax]}
                allowDecimals={false}
                tick={{ fontSize: 11, fill: chartTheme.tick }}
                width={48}
                stroke={chartTheme.grid}
              />
              <Tooltip
                formatter={(value) => [`${value}`, "Stellen"]}
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
                dataKey="count"
                stroke={chartTheme.line}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                name="Stellen"
              />
            </LineChart>
          </ResponsiveContainer>
          {query.data && (
            <div className="detail-chart-source">
              {formatDateOnly(new Date().toISOString().slice(0, 10))} · {points.length} Messpunkt
              {points.length === 1 ? "" : "e"} im gewählten Zeitraum
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default StockJobsTrendChart;
