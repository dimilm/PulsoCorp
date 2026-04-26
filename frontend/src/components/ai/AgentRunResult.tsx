import type { AIRun } from "../../types";
import type {
  FisherResult,
  RedFlagResult,
  ScenarioResult,
  TournamentResult,
} from "./agentTypes";
import { FisherResultView } from "./FisherResultView";
import { RedFlagResultView } from "./RedFlagResultView";
import { ScenarioResultView } from "./ScenarioResultView";
import { TournamentResultView } from "./TournamentResultView";

interface Props {
  run: AIRun;
  currency?: string | null;
}

export function AgentRunResult({ run, currency }: Props) {
  if (run.status === "error") {
    return (
      <div className="ai-result-error" role="alert">
        <strong>Lauf fehlgeschlagen.</strong>
        <p>{run.error_text || "Unbekannter Fehler"}</p>
      </div>
    );
  }
  if (!run.result_payload) {
    return <p className="ai-empty">Keine Daten geliefert.</p>;
  }
  switch (run.agent_id) {
    case "fisher":
      return <FisherResultView result={run.result_payload as unknown as FisherResult} />;
    case "scenario":
      return (
        <ScenarioResultView
          result={run.result_payload as unknown as ScenarioResult}
          currency={currency}
        />
      );
    case "redflag":
      return <RedFlagResultView result={run.result_payload as unknown as RedFlagResult} />;
    case "tournament": {
      // Tournament results store ISINs only — fish the human-readable
      // company names back out of the `input_payload.participants` so the
      // bracket reads "Apple" / "AAPL" instead of just "US0378331005".
      const participants = (run.input_payload as { participants?: unknown })
        ?.participants;
      const participantsByIsin: Record<string, string> = {};
      if (Array.isArray(participants)) {
        for (const p of participants) {
          if (p && typeof p === "object") {
            const isin = (p as { isin?: unknown }).isin;
            const name = (p as { name?: unknown }).name;
            if (typeof isin === "string" && typeof name === "string" && name) {
              participantsByIsin[isin] = name;
            }
          }
        }
      }
      return (
        <TournamentResultView
          result={run.result_payload as unknown as TournamentResult}
          participantsByIsin={participantsByIsin}
        />
      );
    }
    default:
      return (
        <pre className="ai-result-raw">
          {JSON.stringify(run.result_payload, null, 2)}
        </pre>
      );
  }
}
