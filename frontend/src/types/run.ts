export type StepStatus = "not_started" | "running" | "done" | "error" | "cancelled";

export interface RunStep {
  status: StepStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface RunStockStatus {
  isin: string;
  stock_name: string | null;
  overall_status: StepStatus;
  started_at: string | null;
  finished_at: string | null;
  resolved_symbol: string | null;
  symbol: RunStep;
  quote: RunStep;
  metrics: RunStep;
}

export interface RunSummary {
  id: number;
  run_type: "market" | "jobs";
  started_at: string;
  finished_at: string | null;
  duration_seconds: number;
  stocks_total: number;
  stocks_done: number;
  stocks_success: number;
  stocks_error: number;
  phase: "queued" | "running" | "finished";
  status: string;
  error_details: string | null;
}
