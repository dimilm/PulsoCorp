import { useState } from "react";

import { extractApiError } from "../../lib/apiError";
import { formatDate } from "../../lib/format";
import type { AgentInfo, AIRun } from "../../types";
import { Modal } from "../Modal";
import { Spinner } from "../Spinner";
import { AgentRunResult } from "./AgentRunResult";
import { TournamentPeerSelector } from "./TournamentPeerSelector";
import { useAgentPrompt, useAgentRuns, useRunAgent } from "../../hooks/useAIAgents";

interface Props {
  agent: AgentInfo;
  isin: string;
  currency?: string | null;
}

function summariseRun(run: AIRun): string {
  if (run.status === "error") return run.error_text ?? "Fehler";
  const payload = run.result_payload ?? {};
  switch (run.agent_id) {
    case "fisher": {
      const total = (payload as { total_score?: number }).total_score;
      const verdict = (payload as { verdict?: string }).verdict;
      return total != null && verdict
        ? `Score ${total}/30 · ${verdict}`
        : "Fisher-Bewertung";
    }
    case "scenario": {
      const exp = (payload as { expected_return_pct?: number }).expected_return_pct;
      return exp != null ? `Erwartete Rendite ${exp.toFixed(1)} %` : "Szenario-Analyse";
    }
    case "redflag": {
      const flags = (payload as { flags?: unknown[] }).flags?.length ?? 0;
      const overall = (payload as { overall_risk?: string }).overall_risk;
      return `${flags} Flag(s) · Risiko ${overall ?? "?"}`;
    }
    case "tournament": {
      const winner = (payload as { winner_isin?: string }).winner_isin;
      return winner ? `Sieger: ${winner}` : "Turnier";
    }
    default:
      return "Lauf abgeschlossen";
  }
}

export function AgentCard({ agent, isin, currency }: Props) {
  const runsQuery = useAgentRuns(agent.id, isin);
  const runMutation = useRunAgent();
  const [showPrompt, setShowPrompt] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [activeRun, setActiveRun] = useState<AIRun | null>(null);
  const [peers, setPeers] = useState<string[]>([]);
  const [runError, setRunError] = useState<string | null>(null);

  const promptQuery = useAgentPrompt(showPrompt ? agent.id : null);
  const latestRun = runsQuery.data?.[0] ?? null;

  async function execute() {
    setRunError(null);
    try {
      const run = await runMutation.mutateAsync({
        agentId: agent.id,
        isin,
        peers: agent.id === "tournament" && peers.length > 0 ? peers : undefined,
      });
      setActiveRun(run);
      setShowResult(true);
    } catch (err) {
      setRunError(extractApiError(err, "Agent-Lauf fehlgeschlagen."));
    }
  }

  function openLatest() {
    if (latestRun) {
      setActiveRun(latestRun);
      setShowResult(true);
    }
  }

  return (
    <article className="ai-agent-card">
      <header className="ai-agent-card-head">
        <div>
          <h4 className="ai-agent-name">{agent.name}</h4>
          <p className="ai-agent-desc">{agent.description}</p>
        </div>
        <div className="ai-agent-actions">
          <button
            type="button"
            className="btn-link"
            onClick={() => setShowPrompt(true)}
          >
            Prompt
          </button>
          <button
            type="button"
            className="btn-link"
            onClick={() => setShowHistory(true)}
          >
            Verlauf
          </button>
        </div>
      </header>

      {agent.id === "tournament" && (
        <TournamentPeerSelector isin={isin} onChange={setPeers} />
      )}

      <div className="ai-agent-latest">
        {runsQuery.isLoading && <span className="ai-empty">Lade Verlauf…</span>}
        {!runsQuery.isLoading && !latestRun && (
          <span className="ai-empty">Noch kein Lauf vorhanden.</span>
        )}
        {latestRun && (
          <button
            type="button"
            className={`ai-latest-pill ai-latest-${latestRun.status}`}
            onClick={openLatest}
            title="Letzten Lauf öffnen"
          >
            <span className="ai-latest-time">{formatDate(latestRun.created_at)}</span>
            <span className="ai-latest-summary">{summariseRun(latestRun)}</span>
          </button>
        )}
      </div>

      <div className="ai-agent-footer">
        <button
          type="button"
          className="btn-primary"
          onClick={execute}
          disabled={runMutation.isPending}
        >
          {runMutation.isPending ? "Läuft…" : "Ausführen"}
        </button>
        {runError && (
          <span className="ai-agent-error" role="alert">
            {runError}
          </span>
        )}
      </div>

      <Modal
        open={showPrompt}
        onClose={() => setShowPrompt(false)}
        title={`Prompt: ${agent.name}`}
        subtitle="Statisch — nicht editierbar"
      >
        {promptQuery.isLoading ? (
          <Spinner label="Lade Prompt…" />
        ) : promptQuery.isError ? (
          <p className="form-banner-error">Prompt konnte nicht geladen werden.</p>
        ) : (
          <pre className="ai-prompt-text">{promptQuery.data}</pre>
        )}
      </Modal>

      <Modal
        open={showHistory}
        onClose={() => setShowHistory(false)}
        title={`Verlauf: ${agent.name}`}
        subtitle={`Letzte ${runsQuery.data?.length ?? 0} Läufe`}
      >
        {runsQuery.isLoading ? (
          <Spinner label="Lade Verlauf…" />
        ) : !runsQuery.data || runsQuery.data.length === 0 ? (
          <p className="ai-empty">Noch kein Lauf vorhanden.</p>
        ) : (
          <ul className="ai-history-list">
            {runsQuery.data.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  className={`ai-history-item ai-history-${run.status}`}
                  onClick={() => {
                    setActiveRun(run);
                    setShowHistory(false);
                    setShowResult(true);
                  }}
                >
                  <span className="ai-history-time">{formatDate(run.created_at)}</span>
                  <span className="ai-history-summary">{summariseRun(run)}</span>
                  <span className="ai-history-meta">
                    {run.provider} · {run.model}
                    {run.cost_estimate != null && ` · $${run.cost_estimate.toFixed(4)}`}
                    {run.duration_ms != null && ` · ${(run.duration_ms / 1000).toFixed(1)}s`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <Modal
        open={showResult && activeRun != null}
        onClose={() => setShowResult(false)}
        title={`${agent.name} · ${activeRun ? formatDate(activeRun.created_at) : ""}`}
        subtitle={
          activeRun ? (
            <span>
              {activeRun.provider} · {activeRun.model}
              {activeRun.cost_estimate != null && ` · ca. $${activeRun.cost_estimate.toFixed(4)}`}
            </span>
          ) : null
        }
      >
        {activeRun && <AgentRunResult run={activeRun} currency={currency} />}
      </Modal>
    </article>
  );
}
