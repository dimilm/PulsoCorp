import type { RedFlagResult } from "./agentTypes";

const SEVERITY_LABEL: Record<string, string> = {
  low: "Niedrig",
  med: "Mittel",
  high: "Hoch",
};

const CATEGORY_LABEL: Record<string, string> = {
  accounting: "Bilanzierung",
  leverage: "Verschuldung",
  regulatory: "Regulatorik",
  concentration: "Konzentration",
  governance: "Governance",
  market: "Marktumfeld",
  other: "Sonstiges",
};

interface Props {
  result: RedFlagResult;
}

export function RedFlagResultView({ result }: Props) {
  return (
    <div className="ai-result-redflag">
      <div className="ai-result-header">
        <div>
          <span className="ai-result-stat-label">Gesamtrisiko</span>
          <span className={`ai-redflag-severity ai-redflag-${result.overall_risk}`}>
            {SEVERITY_LABEL[result.overall_risk] ?? result.overall_risk}
          </span>
        </div>
        <div>
          <span className="ai-result-stat-label">Anzahl Flags</span>
          <span className="ai-result-stat-value">{result.flags.length}</span>
        </div>
      </div>
      {result.summary && <p className="ai-result-summary">{result.summary}</p>}
      {result.flags.length === 0 ? (
        <p className="ai-empty">Keine Auffälligkeiten gefunden.</p>
      ) : (
        <ul className="ai-redflag-list">
          {result.flags.map((f, idx) => (
            <li key={idx} className={`ai-redflag-item ai-redflag-${f.severity}`}>
              <div className="ai-redflag-head">
                <span className="ai-redflag-title">{f.title}</span>
                <span className={`ai-redflag-severity-pill ai-redflag-${f.severity}`}>
                  {SEVERITY_LABEL[f.severity] ?? f.severity}
                </span>
                <span className="ai-redflag-category">
                  {CATEGORY_LABEL[f.category] ?? f.category}
                </span>
              </div>
              <p className="ai-redflag-desc">{f.description}</p>
              {f.evidence_hint && (
                <p className="ai-redflag-evidence">
                  <strong>Indizien:</strong> {f.evidence_hint}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
