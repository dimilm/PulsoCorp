import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export const STOCKS_QUERY_KEY = ["stocks"] as const;

export interface RefreshKickoff {
  run_id: number | null;
  phase: string | null;
  status: string;
}

// The single-stock refresh now runs on the same background worker as the bulk
// job. The mutation returns the new run id immediately so the caller can poll
// `/run-logs/current` for live progress and a real success/failure result.
// Stock list invalidation happens on run-finish (see RunsPage useEffect),
// so we only refresh the run summary cache here.
export function useRefreshStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (isin: string): Promise<RefreshKickoff> => {
      const res = await api.post(`/stocks/${isin}/refresh`);
      return res.data as RefreshKickoff;
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["run-current"] }),
  });
}

export function useDeleteStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (isin: string) => api.delete(`/stocks/${isin}`),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
      await qc.invalidateQueries({ queryKey: ["tags"] });
    },
  });
}

export function useTriggerRefreshAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/jobs/refresh-all"),
    onSettled: () => qc.invalidateQueries({ queryKey: ["run-current"] }),
  });
}

export function useCancelRefreshAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post("/jobs/refresh-all/cancel");
      return res.data as { cancelled: boolean; run_id?: number; reason?: string };
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["run-current"] }),
  });
}
