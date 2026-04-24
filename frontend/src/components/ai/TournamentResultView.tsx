import type { TournamentResult } from "./agentTypes";

const CATEGORY_LABEL: Record<string, string> = {
  moat: "Burggraben",
  growth: "Wachstum",
  profitability: "Profitabilität",
  balance_sheet: "Bilanz",
  valuation: "Bewertung",
  management: "Management",
  risk: "Risiko",
};

interface Props {
  result: TournamentResult;
}

export function TournamentResultView({ result }: Props) {
  return (
    <div className="ai-result-tournament">
      <div className="ai-result-header">
        <div>
          <span className="ai-result-stat-label">Sieger</span>
          <span className="ai-result-stat-value ai-result-stat-isin">{result.winner_isin}</span>
        </div>
        <div>
          <span className="ai-result-stat-label">Runden</span>
          <span className="ai-result-stat-value">{result.rounds.length}</span>
        </div>
      </div>
      {result.summary && <p className="ai-result-summary">{result.summary}</p>}
      {result.winner_rationale && (
        <p className="ai-result-summary">
          <strong>Begründung:</strong> {result.winner_rationale}
        </p>
      )}
      <div className="ai-tournament-bracket">
        {result.rounds.map((round, ri) => (
          <section key={ri} className="ai-tournament-round">
            <h4 className="ai-tournament-round-title">Runde {ri + 1}</h4>
            <div className="ai-tournament-matches">
              {round.map((match, mi) => (
                <details key={mi} className="ai-tournament-match" open>
                  <summary>
                    <span className={match.winner === match.a ? "ai-tournament-side ai-winner" : "ai-tournament-side"}>
                      {match.a}
                    </span>
                    <span className="ai-tournament-vs">vs</span>
                    <span className={match.winner === match.b ? "ai-tournament-side ai-winner" : "ai-tournament-side"}>
                      {match.b}
                    </span>
                  </summary>
                  <table className="ai-tournament-scores">
                    <thead>
                      <tr>
                        <th>Kategorie</th>
                        <th>{match.a}</th>
                        <th>{match.b}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(match.category_scores).map(([cat, score]) => (
                        <tr key={cat}>
                          <td>{CATEGORY_LABEL[cat] ?? cat}</td>
                          <td>{score.a}</td>
                          <td>{score.b}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {match.rationale && <p className="ai-tournament-rationale">{match.rationale}</p>}
                </details>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
