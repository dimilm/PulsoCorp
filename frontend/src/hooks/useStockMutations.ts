import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export const STOCKS_QUERY_KEY = ["stocks"] as const;

function useInvalidateStocks() {
  const qc = useQueryClient();
  return async () => {
    await qc.invalidateQueries({ queryKey: STOCKS_QUERY_KEY });
    await qc.invalidateQueries({ queryKey: ["tags"] });
  };
}

export function useRefreshStock() {
  const invalidate = useInvalidateStocks();
  return useMutation({
    mutationFn: (isin: string) => api.post(`/stocks/${isin}/refresh`),
    onSuccess: invalidate,
  });
}

export function useEvaluateStock() {
  const invalidate = useInvalidateStocks();
  return useMutation({
    mutationFn: (isin: string) => api.post(`/ai/evaluate/${isin}?apply=true`),
    onSuccess: invalidate,
  });
}

export function usePreviewEvaluate() {
  return useMutation({
    mutationFn: async (isin: string) => {
      const res = await api.post(`/ai/evaluate/${isin}?apply=false`);
      return { isin, ...res.data } as Record<string, unknown> & { isin: string };
    },
  });
}

export function useToggleLock() {
  const invalidate = useInvalidateStocks();
  return useMutation({
    mutationFn: (vars: { isin: string; field: string; locked: boolean }) =>
      api.post(`/stocks/${vars.isin}/lock`, {
        field_names: [vars.field],
        locked: vars.locked,
      }),
    onSuccess: invalidate,
  });
}

export function useDeleteStock() {
  const invalidate = useInvalidateStocks();
  return useMutation({
    mutationFn: (isin: string) => api.delete(`/stocks/${isin}`),
    onSuccess: invalidate,
  });
}

export function useTriggerRefreshAll() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post("/jobs/refresh-all"),
    onSettled: () => qc.invalidateQueries({ queryKey: ["run-current"] }),
  });
}
