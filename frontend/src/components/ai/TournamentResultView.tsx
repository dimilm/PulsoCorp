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
  // Map ISIN → human-readable company name. Built in `AgentRunResult` from
  // the run's `input_payload.participants`. Bracket entries store ISINs
  // only, so without this lookup the table heads/match summaries would
  // just be opaque country-prefixed identifiers.
  participantsByIsin?: Record<string, string>;
}

export function TournamentResultView({ result, participantsByIsin }: Props) {
  function nameFor(isin: string): string {
    return participantsByIsin?.[isin] ?? isin;
  }
  function renderSide(isin: string): JSX.Element {
    const name = nameFor(isin);
    if (name === isin) {
      return <span className="ai-tournament-side-name">{isin}</span>;
    }
    return (
      <>
        <span className="ai-tournament-side-name">{name}</span>
        <span className="ai-tournament-side-isin">{isin}</span>
      </>
    );
  }

  return (
    <div className="ai-result-tournament">
      <div className="ai-result-header">
        <div>
          <span className="ai-result-stat-label">Sieger</span>
          <span className="ai-result-stat-value ai-result-stat-isin">
            {nameFor(result.winner_isin)}
          </span>
          {nameFor(result.winner_isin) !== result.winner_isin && (
            <span className="ai-result-stat-sub">{result.winner_isin}</span>
          )}
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
                    <span
                      className={
                        match.winner === match.a
                          ? "ai-tournament-side ai-winner"
                          : "ai-tournament-side"
                      }
                    >
                      {renderSide(match.a)}
                    </span>
                    <span className="ai-tournament-vs">vs</span>
                    <span
                      className={
                        match.winner === match.b
                          ? "ai-tournament-side ai-winner"
                          : "ai-tournament-side"
                      }
                    >
                      {renderSide(match.b)}
                    </span>
                  </summary>
                  <table className="ai-tournament-scores">
                    <thead>
                      <tr>
                        <th>Kategorie</th>
                        <th title={match.a}>{nameFor(match.a)}</th>
                        <th title={match.b}>{nameFor(match.b)}</th>
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
