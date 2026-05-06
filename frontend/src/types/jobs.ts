import type { StepStatus } from "./run";

export const JOB_ADAPTER_TYPES = [
  "static_html",
  "static_text_regex",
  "json_get_path_int",
  "json_get_array_count",
  "json_post_path_int",
  "json_post_facet_sum",
  "playwright_api_fetch",
  "playwright_css_count",
  "playwright_text_regex",
] as const;

export type JobAdapterType = (typeof JOB_ADAPTER_TYPES)[number];

export const PLAYWRIGHT_ADAPTER_TYPES: readonly JobAdapterType[] = [
  "playwright_api_fetch",
  "playwright_css_count",
  "playwright_text_regex",
];

export function isPlaywrightAdapter(type: JobAdapterType): boolean {
  return (PLAYWRIGHT_ADAPTER_TYPES as readonly string[]).includes(type);
}

export interface JobSource {
  id: number;
  isin: string | null;
  name: string;
  portal_url: string;
  adapter_type: JobAdapterType;
  adapter_settings: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  latest_count: number | null;
  latest_snapshot_date: string | null;
  delta_7d: number | null;
  delta_30d: number | null;
}

export interface JobSnapshot {
  id: number;
  job_source_id: number;
  snapshot_date: string;
  jobs_count: number;
  recorded_at: string;
  run_id: number | null;
  raw_meta: Record<string, unknown>;
}

export interface JobSourceTrend {
  source_id: number;
  days: number;
  points: JobSnapshot[];
}

export interface JobSourceTestResult {
  status: "ok" | "error";
  jobs_count: number | null;
  error: string | null;
  duration_ms: number;
  raw_meta: Record<string, unknown> | null;
}

export interface StockJobs {
  isin: string;
  sources: JobSource[];
  total_latest: number | null;
  total_delta_7d: number | null;
  total_delta_30d: number | null;
}

export interface JobsTrendPoint {
  snapshot_date: string;
  jobs_count: number;
}

export interface StockJobsTrend {
  isin: string;
  days: number;
  points: JobsTrendPoint[];
}

export interface RunJobStatus {
  job_source_id: number;
  source_name: string | null;
  isin: string | null;
  overall_status: StepStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  jobs_count: number | null;
  error: string | null;
}

export interface JobRefreshResponse {
  run_id: number | null;
  phase: string | null;
  status: string;
}

export type JobSourceCreate = Pick<
  JobSource,
  "isin" | "name" | "portal_url" | "adapter_type" | "adapter_settings" | "is_active"
>;

export type JobSourceUpdate = Partial<JobSourceCreate>;
