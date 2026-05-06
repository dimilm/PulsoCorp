import { useMemo } from "react";
import { useJobSources } from "./useJobSources";
import {
  useJobsTrendsAggregate,
  type JobsTrendPoint,
} from "./useJobsTrendsAggregate";

export interface JobsAggregate {
  latest: number | null;
  delta_7d: number | null;
}

export const JOBS_TREND_DAYS = 90;

/** Always-on aggregator for the watchlist `Stellen` column.
 *
 *  Fetches the per-source list and the per-ISIN 90-day trend in parallel
 *  and reshapes both into ISIN-keyed maps. The column is no longer
 *  toggleable — it's part of the default watchlist surface — so this
 *  hook returns plain data without any visibility flag.
 */
export function useJobsAggregate() {
  const jobSourcesQuery = useJobSources({});
  const trendsQuery = useJobsTrendsAggregate(true, JOBS_TREND_DAYS);

  const jobsByIsin = useMemo<Record<string, JobsAggregate>>(() => {
    const sources = jobSourcesQuery.data ?? [];
    const map: Record<string, JobsAggregate> = {};
    for (const source of sources) {
      if (!source.isin) continue;
      const slot = map[source.isin] ?? { latest: null, delta_7d: null };
      if (source.latest_count != null) {
        slot.latest = (slot.latest ?? 0) + source.latest_count;
      }
      if (source.delta_7d != null) {
        slot.delta_7d = (slot.delta_7d ?? 0) + source.delta_7d;
      }
      map[source.isin] = slot;
    }
    return map;
  }, [jobSourcesQuery.data]);

  const trendsByIsin = useMemo<Record<string, JobsTrendPoint[]>>(
    () => trendsQuery.data ?? {},
    [trendsQuery.data]
  );

  return { jobsByIsin, trendsByIsin };
}
