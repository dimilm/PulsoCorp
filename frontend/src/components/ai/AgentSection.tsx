import { useEffect, useMemo, useState } from "react";

import { extractApiError } from "../../lib/apiError";
import { formatDate } from "../../lib/format";
import type { AgentInfo, AIRun } from "../../types";
import { EmptyState } from "../EmptyState";
import { Modal } from "../Modal";
import { Spinner } from "../Spinner";
import { AgentRunResult } from "./AgentRunResult";
import { TournamentPeerSelector } from "./TournamentPeerSelector";
import { useAgentPrompt, useRunAgent } from "../../hooks/useAIAgents";

interface Props {
  agent: AgentInfo;
  runs: AIRun[];
  isin: string;
  currency?: string | null;
  isExpanded: boolean;
  onToggle: () => void;
  onExpand: () => void;
}

// Look up a Tournament participant's company name by its ISIN. The bracket
// payload only stores ISINs, but `input_payload.participants` keeps the
// original `[{isin, name, …}]` list — fall back to the ISIN when no name
// was captured (defensive: legacy runs without participant names).
function tournamentParticipantName(run: AIRun, isin: string): string {
  const participants = (run.input_payload as { participants?: unknown })
    ?.participants;
  if (Array.isArray(participants)) {
    for (const p of participants) {
      if (
        p &&
        typeof p === "object" &&
        (p as { isin?: unknown }).isin === isin &&
        typeof (p as { name?: unknown }).name === "string" &&
        (p as { name: string }).name
      ) {
        return (p as { name: string }).name;
      }
    }
  }
  return isin;
}

function summariseRun(run: AIRun): string {
  if (run.status === "running") return "läuft …";
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
      if (!winner) return "Turnier";
      const name = tournamentParticipantName(run, winner);
      return name === winner ? `Sieger: ${winner}` : `Sieger: ${name}`;
    }
    default:
      return "Lauf abgeschlossen";
  }
}

export function AgentSection({
  agent,
  runs,
  isin,
  currency,
  isExpanded,
  onToggle,
  onExpand,
}: Props) {
  const runMutation = useRunAgent();
  const [showPrompt, setShowPrompt] = useState(false);
  const [peers, setPeers] = useState<string[]>([]);
  const [runError, setRunError] = useState<string | null>(null);
  const [pickedRunId, setPickedRunId] = useState<number | null>(null);

  const promptQuery = useAgentPrompt(showPrompt ? agent.id : null);
  const latestRun = runs[0] ?? null;

  // Effective selection: explicit pick wins, otherwise track latest so the
  // section auto-advances from "running" to "done" without the user having
  // to re-select anything.
  const selectedRun = useMemo<AIRun | null>(() => {
    if (pickedRunId == null) return latestRun;
    return runs.find((r) => r.id === pickedRunId) ?? latestRun;
  }, [pickedRunId, runs, latestRun]);

  // If a manually-picked run drops out of the list (e.g. cleanup), forget
  // the explicit selection so we fall back to the newest one.
  useEffect(() => {
    if (pickedRunId != null && !runs.some((r) => r.id === pickedRunId)) {
      setPickedRunId(null);
    }
  }, [pickedRunId, runs]);

  async function execute() {
    setRunError(null);
    try {
      const run = await runMutation.mutateAsync({
        agentId: agent.id,
        isin,
        peers: agent.id === "tournament" && peers.length > 0 ? peers : undefined,
      });
      setPickedRunId(run.id);
      if (!isExpanded) onExpand();
    } catch (err) {
      setRunError(extractApiError(err, "Agent-Lauf konnte nicht gestartet werden."));
    }
  }

  const isRunning = latestRun?.status === "running";
  const buttonDisabled = runMutation.isPending || isRunning;
  const statusLabel = latestRun
    ? latestRun.status === "running"
      ? "läuft …"
      : summariseRun(latestRun)
    : "Noch kein Lauf";
  const statusClass = latestRun
    ? `ai-status-${latestRun.status}`
    : "ai-status-empty";

  return (
    <article
      className={`ai-agent-section ${isExpanded ? "is-expanded" : "is-collapsed"}`}
    >
      <header className="ai-agent-section-head">
        <button
          type="button"
          className="ai-agent-section-toggle"
          onClick={onToggle}
          aria-expanded={isExpanded}
          aria-label={`${agent.name}: ${isExpanded ? "Section schließen" : "Section öffnen"}`}
        >
          <span className="ai-agent-section-chevron" aria-hidden="true">
            {isExpanded ? "▾" : "▸"}
          </span>
          <span className="ai-agent-section-title">
            <span className="ai-agent-name">{agent.name}</span>
            <span className="ai-agent-desc">{agent.description}</span>
          </span>
        </button>
        <span className={`ai-status-pill ${statusClass}`} title={latestRun ? formatDate(latestRun.created_at) : undefined}>
          {statusLabel}
        </span>
        <div className="ai-agent-section-actions">
          {runs.length > 0 && (
            <select
              className="ai-run-picker"
              value={selectedRun?.id ?? ""}
              onChange={(e) => setPickedRunId(Number(e.target.value))}
              aria-label="Vorherigen Lauf wählen"
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {formatDate(r.created_at)} · {summariseRun(r)}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            className="btn-link"
            onClick={() => setShowPrompt(true)}
          >
            Prompt
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={execute}
            disabled={buttonDisabled}
          >
            {buttonDisabled ? "Läuft…" : "Ausführen"}
          </button>
        </div>
      </header>

      {isExpanded && (
        <div className="ai-agent-section-body">
          {agent.id === "tournament" && (
            <TournamentPeerSelector isin={isin} onChange={setPeers} />
          )}
          {selectedRun ? (
            <>
              <div className="ai-result-meta">
                <span>{selectedRun.provider}</span>
                <span>·</span>
                <span>{selectedRun.model}</span>
                {selectedRun.cost_estimate != null && (
                  <>
                    <span>·</span>
                    <span>ca. ${selectedRun.cost_estimate.toFixed(4)}</span>
                  </>
                )}
                {selectedRun.duration_ms != null && selectedRun.status !== "running" && (
                  <>
                    <span>·</span>
                    <span>{(selectedRun.duration_ms / 1000).toFixed(1)}s</span>
                  </>
                )}
                <span>·</span>
                <span>{formatDate(selectedRun.created_at)}</span>
              </div>
              {selectedRun.status === "running" ? (
                <RunningPlaceholder startedAt={selectedRun.created_at} />
              ) : (
                <AgentRunResult run={selectedRun} currency={currency} />
              )}
            </>
          ) : (
            <EmptyState
              variant="inline"
              title="Noch kein Lauf vorhanden"
              description="Starte mit „Ausführen“ eine erste Analyse."
            />
          )}
          {runError && (
            <p className="form-banner-error" role="alert">
              {runError}
            </p>
          )}
        </div>
      )}

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
    </article>
  );
}

interface RunningPlaceholderProps {
  startedAt: string;
}

// Live "läuft seit Xs"-counter for an in-flight run. Mirrors the approach used
// by the refresh-status card (`liveRunSeconds`): naive ISO strings from the
// backend get parsed by `new Date()` which interprets them as local time —
// good enough for a one-second resolution, identical to the rest of the app.
function RunningPlaceholder({ startedAt }: RunningPlaceholderProps) {
  const startMs = useMemo(() => new Date(startedAt).getTime(), [startedAt]);
  const [elapsed, setElapsed] = useState(() => {
    if (Number.isNaN(startMs)) return 0;
    return Math.max(0, Math.floor((Date.now() - startMs) / 1000));
  });
  useEffect(() => {
    if (Number.isNaN(startMs)) return;
    const handle = window.setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    }, 1000);
    return () => window.clearInterval(handle);
  }, [startMs]);
  return (
    <div className="ai-result-running-block" role="status" aria-live="polite">
      <Spinner label={`Analyse läuft … (seit ${elapsed}s)`} />
      <p className="ai-result-running-hint">
        Die Antwort des LLM dauert je nach Provider und Modell typischerweise
        mehrere Sekunden bis ein paar Minuten. Du kannst die Seite verlassen –
        das Ergebnis erscheint beim nächsten Aufruf automatisch.
      </p>
    </div>
  );
}

export default AgentSection;
