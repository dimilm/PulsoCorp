import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type {
  JobRefreshResponse,
  JobSource,
  JobSourceCreate,
  JobSourceTestResult,
  JobSourceTrend,
  JobSourceUpdate,
  RunJobStatus,
  StockJobs,
  StockJobsTrend,
} from "../types/jobs";

export const JOB_SOURCES_KEY = ["job-sources"] as const;
export const JOB_SOURCE_DETAIL_KEY = (id: number) =>
  [...JOB_SOURCES_KEY, "detail", id] as const;
export const JOB_SOURCE_TREND_KEY = (id: number, days: number) =>
  [...JOB_SOURCES_KEY, "trend", id, days] as const;
export const STOCK_JOBS_KEY = (isin: string) => ["stock-jobs", isin] as const;
export const RUN_JOB_STATUSES_KEY = (runId: number) =>
  ["run-logs", runId, "jobs"] as const;

export function useJobSources(filters?: {
  isin?: string | null;
  is_active?: boolean | null;
}, options?: { polling?: boolean }) {
  return useQuery<JobSource[]>({
    queryKey: [...JOB_SOURCES_KEY, "list", filters?.isin ?? null, filters?.is_active ?? null],
    queryFn: async () => {
      const params: Record<string, string | boolean> = {};
      if (filters?.isin) params.isin = filters.isin;
      if (typeof filters?.is_active === "boolean") params.is_active = filters.is_active;
      const res = await api.get("/job-sources", { params });
      return res.data as JobSource[];
    },
    refetchInterval: options?.polling ? 2000 : false,
    staleTime: 30_000,
  });
}

export function useJobSource(id: number | undefined) {
  return useQuery<JobSource>({
    queryKey: JOB_SOURCE_DETAIL_KEY(id ?? -1),
    enabled: id != null && id >= 0,
    queryFn: async () => {
      const res = await api.get(`/job-sources/${id}`);
      return res.data as JobSource;
    },
    staleTime: 30_000,
  });
}

export function useJobSourceTrend(id: number | undefined, days = 30) {
  return useQuery<JobSourceTrend>({
    queryKey: JOB_SOURCE_TREND_KEY(id ?? -1, days),
    enabled: id != null && id >= 0,
    queryFn: async () => {
      const res = await api.get(`/job-sources/${id}/trend`, { params: { days } });
      return res.data as JobSourceTrend;
    },
    staleTime: 60_000,
  });
}

export function useStockJobs(isin: string | undefined) {
  return useQuery<StockJobs>({
    queryKey: STOCK_JOBS_KEY(isin ?? ""),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/stocks/${isin}/jobs`);
      return res.data as StockJobs;
    },
    staleTime: 30_000,
  });
}

export const STOCK_JOBS_TREND_KEY = (isin: string, days: number) =>
  ["stock-jobs", isin, "trend", days] as const;

export function useStockJobsTrend(isin: string | undefined, days: number) {
  return useQuery<StockJobsTrend>({
    queryKey: STOCK_JOBS_TREND_KEY(isin ?? "", days),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/stocks/${isin}/jobs/trend`, { params: { days } });
      return res.data as StockJobsTrend;
    },
    staleTime: 60_000,
  });
}

export function useRunJobStatuses(runId: number | undefined, polling = false) {
  return useQuery<RunJobStatus[]>({
    queryKey: RUN_JOB_STATUSES_KEY(runId ?? -1),
    enabled: runId != null && runId >= 0,
    queryFn: async () => {
      const res = await api.get(`/run-logs/${runId}/jobs`);
      return res.data as RunJobStatus[];
    },
    // While the run is in progress the JobsPage polls every couple of
    // seconds; once finished the cache is honoured for 30s like the
    // refresh-pipeline mirror endpoint.
    refetchInterval: polling ? 2000 : false,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

function invalidateJobSources(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: JOB_SOURCES_KEY });
  qc.invalidateQueries({ queryKey: ["stock-jobs"] });
}

function invalidateJobsRunQueries(
  qc: ReturnType<typeof useQueryClient>,
  runId: number | null | undefined
) {
  // JobsPage reads `useCurrentRun("jobs")` from this key.
  qc.invalidateQueries({ queryKey: ["run-current", "jobs"] });
  qc.invalidateQueries({ queryKey: ["run-logs"] });
  if (runId != null && runId >= 0) {
    qc.invalidateQueries({ queryKey: RUN_JOB_STATUSES_KEY(runId) });
  }
}

export function useCreateJobSource() {
  const qc = useQueryClient();
  return useMutation<JobSource, Error, JobSourceCreate>({
    mutationFn: async (payload) => {
      const res = await api.post("/job-sources", payload);
      return res.data as JobSource;
    },
    onSuccess: () => invalidateJobSources(qc),
  });
}

export function useUpdateJobSource(id: number) {
  const qc = useQueryClient();
  return useMutation<JobSource, Error, JobSourceUpdate>({
    mutationFn: async (payload) => {
      const res = await api.patch(`/job-sources/${id}`, payload);
      return res.data as JobSource;
    },
    onSuccess: () => invalidateJobSources(qc),
  });
}

export function useDeleteJobSource() {
  const qc = useQueryClient();
  return useMutation<void, Error, number>({
    mutationFn: async (id) => {
      await api.delete(`/job-sources/${id}`);
    },
    onSuccess: () => invalidateJobSources(qc),
  });
}

export function useTestJobSource() {
  return useMutation<JobSourceTestResult, Error, number>({
    mutationFn: async (id) => {
      const res = await api.post(`/job-sources/${id}/test`);
      return res.data as JobSourceTestResult;
    },
  });
}

export function useRefreshJobSource() {
  const qc = useQueryClient();
  return useMutation<JobRefreshResponse, Error, number>({
    mutationFn: async (id) => {
      const res = await api.post(`/job-sources/${id}/refresh`);
      return res.data as JobRefreshResponse;
    },
    onSuccess: (res) => {
      invalidateJobSources(qc);
      invalidateJobsRunQueries(qc, res.run_id);
    },
  });
}

export function useRefreshAllJobs() {
  const qc = useQueryClient();
  return useMutation<JobRefreshResponse, Error, void>({
    mutationFn: async () => {
      const res = await api.post("/jobs-runs/refresh-all");
      return res.data as JobRefreshResponse;
    },
    onSuccess: (res) => {
      invalidateJobSources(qc);
      invalidateJobsRunQueries(qc, res.run_id);
    },
  });
}

export function useCancelJobsRefresh() {
  const qc = useQueryClient();
  return useMutation<{ cancelled: boolean; run_id?: number | null }, Error, void>({
    mutationFn: async () => {
      const res = await api.post("/jobs-runs/refresh-all/cancel");
      return res.data as { cancelled: boolean; run_id?: number | null };
    },
    onSuccess: (res) => invalidateJobsRunQueries(qc, res.run_id),
  });
}
