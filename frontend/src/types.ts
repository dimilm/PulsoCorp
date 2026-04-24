export type Recommendation = "none" | "buy" | "risk_buy";

export interface Stock {
  isin: string;
  name: string;
  sector: string | null;
  currency: string | null;
  burggraben: boolean;
  reasoning: string | null;
  tranches: number;
  current_price: number | null;
  day_change_pct: number | null;
  last_updated: string | null;
  last_status: string | null;
  recommendation: Recommendation;
  recommendation_reason?: string | null;
  fundamental_score: number | null;
  moat_score: number | null;
  moat_text?: string | null;
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
  field_sources: Record<string, string>;
  field_locks: Record<string, boolean>;
  dcf_discount_pct: number | null;
  nav_discount_pct: number | null;
  analyst_target_distance_pct: number | null;
  invested_capital_eur: number;
  tags: string[];
}

export interface Tag {
  id: number;
  name: string;
  count: number;
}
