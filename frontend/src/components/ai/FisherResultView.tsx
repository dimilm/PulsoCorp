import type { FisherResult } from "./agentTypes";

const VERDICT_LABEL: Record<string, string> = {
  strong: "Stark",
  neutral: "Neutral",
  weak: "Schwach",
};

const RATING_LABEL: Record<number, string> = {
  0: "Schwach",
  1: "Gemischt",
  2: "Stark",
};

interface Props {
  result: FisherResult;
}

export function FisherResultView({ result }: Props) {
  return (
    <div className="ai-result-fisher">
      <div className="ai-result-header">
        <div>
          <span className="ai-result-stat-label">Gesamtscore</span>
          <span className="ai-result-stat-value">
            {result.total_score}
            <span className="ai-result-stat-max">/30</span>
          </span>
        </div>
        <span className={`ai-result-verdict ai-result-verdict-${result.verdict}`}>
          {VERDICT_LABEL[result.verdict] ?? result.verdict}
        </span>
      </div>
      {result.summary && <p className="ai-result-summary">{result.summary}</p>}
      <table className="ai-result-table">
        <thead>
          <tr>
            <th>Frage</th>
            <th>Bewertung</th>
            <th>Begründung</th>
          </tr>
        </thead>
        <tbody>
          {result.questions.map((q) => (
            <tr key={q.id}>
              <td>{q.question}</td>
              <td>
                <span className={`ai-rating ai-rating-${q.rating}`}>
                  {q.rating} · {RATING_LABEL[q.rating]}
                </span>
              </td>
              <td>{q.rationale}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
