/**
 * Mirrors of the agent Pydantic schemas. Keep in sync with
 * `backend/app/agents/<agent>/schema.py`. We only model what the UI actually
 * renders.
 */

export type FisherVerdict = "strong" | "neutral" | "weak";

export interface FisherQuestion {
  id: string;
  question: string;
  rating: 0 | 1 | 2;
  rationale: string;
}

export interface FisherResult {
  questions: FisherQuestion[];
  total_score: number;
  verdict: FisherVerdict;
  summary: string;
}

export interface ScenarioBranch {
  assumptions: string[];
  target_price: number;
  probability: number;
}

export interface ScenarioResult {
  bull: ScenarioBranch;
  base: ScenarioBranch;
  bear: ScenarioBranch;
  expected_value: number;
  expected_return_pct: number;
  time_horizon_years: number;
  summary: string;
}

export type RedFlagCategory =
  | "accounting"
  | "leverage"
  | "regulatory"
  | "concentration"
  | "governance"
  | "market"
  | "other";

export type RedFlagSeverity = "low" | "med" | "high";

export interface RedFlag {
  category: RedFlagCategory;
  severity: RedFlagSeverity;
  title: string;
  description: string;
  evidence_hint: string;
}

export interface RedFlagResult {
  flags: RedFlag[];
  overall_risk: RedFlagSeverity;
  summary: string;
}

export interface TournamentMatchScore {
  a: number;
  b: number;
}

export interface TournamentMatch {
  a: string;
  b: string;
  category_scores: Record<string, TournamentMatchScore>;
  winner: string;
  rationale: string;
}

export interface TournamentResult {
  rounds: TournamentMatch[][];
  winner_isin: string;
  winner_rationale: string;
  summary: string;
}
