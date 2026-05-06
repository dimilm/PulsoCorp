export type AIAgentId = "fisher" | "scenario" | "redflag" | "tournament";

export interface FisherPillSummary {
  score: number;
  verdict: "strong" | "neutral" | "weak";
}

export interface RedFlagPillSummary {
  overall_risk: "low" | "med" | "high";
  flag_count: number;
}

export interface ScenarioPillSummary {
  expected_return_pct: number;
}

export interface TournamentPillSummary {
  is_winner: boolean;
  winner_isin: string;
  peer_count: number;
}

export type AIPillSummary =
  | FisherPillSummary
  | RedFlagPillSummary
  | ScenarioPillSummary
  | TournamentPillSummary;

export interface AILatestRun {
  agent_id: string;
  created_at: string;
  model: string;
  summary: Record<string, unknown>;
}

export interface Stock {
  isin: string;
  name: string;
  sector: string | null;
  currency: string | null;
  reasoning: string | null;
  ticker_override?: string | null;
  link_yahoo?: string | null;
  link_finanzen?: string | null;
  link_onvista_chart?: string | null;
  link_onvista_fundamental?: string | null;
  tranches: number;
  current_price: number | null;
  day_change_pct: number | null;
  last_updated: string | null;
  last_status: string | null;
  pe_forward: number | null;
  pe_min_5y: number | null;
  pe_max_5y: number | null;
  pe_avg_5y: number | null;
  dividend_yield_current: number | null;
  dividend_yield_avg_5y: number | null;
  analyst_target_1y: number | null;
  market_cap: number | null;
  equity_ratio: number | null;
  debt_ratio: number | null;
  revenue_growth: number | null;
  missing_metrics: string[];
  analyst_target_distance_pct: number | null;
  invested_capital_eur: number;
  tags: string[];
  latest_ai_runs: Partial<Record<AIAgentId, AILatestRun>>;
}

export interface Tag {
  id: number;
  name: string;
  count: number;
}

export type HistoryRange = "1m" | "6m" | "1y" | "5y" | "max";

export interface HistoryPoint {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface HistoryResponse {
  isin: string;
  range: HistoryRange;
  interval: string;
  points: HistoryPoint[];
  fetched_at: string | null;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  output_schema: Record<string, unknown>;
}

export type AIRunStatus = "done" | "error" | "running";

export interface AIRun {
  id: number;
  isin: string;
  agent_id: string;
  created_at: string;
  provider: string;
  model: string;
  status: AIRunStatus;
  input_payload: Record<string, unknown>;
  result_payload: Record<string, unknown> | null;
  error_text: string | null;
  cost_estimate: number | null;
  duration_ms: number | null;
}
