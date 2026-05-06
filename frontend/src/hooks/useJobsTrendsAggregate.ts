import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export interface JobsTrendPoint {
  date: string;
  count: number;
}

interface RawTrendPoint {
  snapshot_date: string;
  jobs_count: number;
}

interface RawTrendItem {
  isin: string;
  points: RawTrendPoint[];
}

interface RawTrendsResponse {
  days: number;
  items: RawTrendItem[];
}

export const JOBS_TRENDS_AGGREGATE_KEY = (days: number) =>
  ["jobs-trends-aggregate", days] as const;

/** Fetches per-ISIN, per-day summed job counts powering the watchlist
 *  sparkline column. Gated behind the same toggle (`showJobsColumn`) as
 *  `useJobsAggregate` so users who hide the column do not pay for the
 *  call. The response is reshaped from the wire format
 *  (`snapshot_date`, `jobs_count`) into the shorter (`date`, `count`)
 *  shape used by the recharts component. */
export function useJobsTrendsAggregate(enabled: boolean, days = 90) {
  return useQuery<Record<string, JobsTrendPoint[]>>({
    queryKey: JOBS_TRENDS_AGGREGATE_KEY(days),
    enabled,
    queryFn: async () => {
      const res = await api.get("/job-sources/trends", { params: { days } });
      const body = res.data as RawTrendsResponse;
      const out: Record<string, JobsTrendPoint[]> = {};
      for (const item of body.items) {
        out[item.isin] = item.points.map((p) => ({
          date: p.snapshot_date,
          count: p.jobs_count,
        }));
      }
      return out;
    },
    staleTime: 60_000,
  });
}
