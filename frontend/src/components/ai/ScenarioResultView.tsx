import { formatCurrency } from "../../lib/format";
import type { ScenarioResult } from "./agentTypes";

interface Props {
  result: ScenarioResult;
  currency?: string | null;
}

// Scenario probabilities/returns arrive as fractions (0..1); render as a
// rounded percentage. The shared formatPercent helper expects pre-multiplied
// values, so we keep this thin local wrapper.
function formatPct(value: number): string {
  return `${(value * 100).toFixed(0)} %`;
}

export function ScenarioResultView({ result, currency }: Props) {
  const cases: { key: "bull" | "base" | "bear"; label: string; data: ScenarioResult["bull"] }[] = [
    { key: "bull", label: "Bull", data: result.bull },
    { key: "base", label: "Base", data: result.base },
    { key: "bear", label: "Bear", data: result.bear },
  ];

  return (
    <div className="ai-result-scenario">
      <div className="ai-result-header">
        <div>
          <span className="ai-result-stat-label">Erwartungswert</span>
          <span className="ai-result-stat-value">{formatCurrency(result.expected_value, currency)}</span>
        </div>
        <div>
          <span className="ai-result-stat-label">Erwartete Rendite</span>
          <span className="ai-result-stat-value">
            {result.expected_return_pct > 0 ? "+" : ""}
            {result.expected_return_pct.toFixed(2)} %
          </span>
        </div>
        <div>
          <span className="ai-result-stat-label">Horizont</span>
          <span className="ai-result-stat-value">{result.time_horizon_years} J</span>
        </div>
      </div>
      {result.summary && <p className="ai-result-summary">{result.summary}</p>}
      <div className="ai-scenario-grid">
        {cases.map((c) => (
          <div key={c.key} className={`ai-scenario-card ai-scenario-${c.key}`}>
            <div className="ai-scenario-card-head">
              <span className="ai-scenario-label">{c.label}</span>
              <span className="ai-scenario-prob">{formatPct(c.data.probability)}</span>
            </div>
            <div className="ai-scenario-target">
              <span className="ai-result-stat-label">Kursziel</span>
              <span className="ai-result-stat-value">{formatCurrency(c.data.target_price, currency)}</span>
            </div>
            <ul className="ai-scenario-assumptions">
              {c.data.assumptions.map((a, idx) => (
                <li key={idx}>{a}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
