import {
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";

import { useChartTheme } from "../../hooks/useChartTheme";
import type { JobsTrendPoint } from "../../hooks/useJobsTrendsAggregate";

interface JobsSparklineProps {
  points: JobsTrendPoint[];
  width?: number;
  height?: number;
}

/** Tiny axis-less recharts line for the watchlist `Stellen` column.
 *
 *  Intentionally no grid, no tooltip, no dots — the cell's `title`
 *  attribute carries the textual context (latest, Δ7T, min/max) and the
 *  StockJobsCard owns the rich drill-down chart. Caller must guarantee
 *  ≥2 data points; with fewer, recharts renders an empty box. */
export function JobsSparkline({
  points,
  width = 96,
  height = 28,
}: JobsSparklineProps) {
  const theme = useChartTheme();
  if (points.length < 2) return null;
  return (
    <div
      className="jobs-sparkline"
      style={{ width, height }}
      aria-hidden="true"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={points}
          margin={{ top: 2, right: 2, bottom: 2, left: 2 }}
        >
          <Line
            type="monotone"
            dataKey="count"
            stroke={theme.line}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default JobsSparkline;
