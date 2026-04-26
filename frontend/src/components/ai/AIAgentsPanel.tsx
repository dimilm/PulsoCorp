import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useAgentRuns, useAgents } from "../../hooks/useAIAgents";
import { useStock } from "../../hooks/useStockQueries";
import type { AgentInfo } from "../../types";
import { Spinner } from "../Spinner";
import { AgentSection } from "./AgentSection";

interface Props {
  isin: string;
}

// Backend ships exactly these four agents; we hard-code the order so the
// stacked sections always appear in the same sequence and so the four
// `useAgentRuns` calls below stay rules-of-hooks compliant (fixed count).
const AGENT_ORDER = ["fisher", "scenario", "redflag", "tournament"] as const;
type AgentId = (typeof AGENT_ORDER)[number];

export function AIAgentsPanel({ isin }: Props) {
  const agentsQuery = useAgents();
  const stockQuery = useStock(isin);
  const currency = stockQuery.data?.currency ?? null;

  // Watchlist pills deep-link to `/stocks/:isin?agent=fisher` so the
  // matching section is already expanded on arrival. Anything other than a
  // known agent id is ignored — `requestedAgent` then stays `null` and the
  // existing auto-expand logic (newest run) takes over.
  const [searchParams] = useSearchParams();
  const requestedAgentRaw = searchParams.get("agent");
  const requestedAgent: AgentId | null = (
    AGENT_ORDER as readonly string[]
  ).includes(requestedAgentRaw ?? "")
    ? (requestedAgentRaw as AgentId)
    : null;

  const fisherRunsQ = useAgentRuns("fisher", isin);
  const scenarioRunsQ = useAgentRuns("scenario", isin);
  const redflagRunsQ = useAgentRuns("redflag", isin);
  const tournamentRunsQ = useAgentRuns("tournament", isin);

  const runsByAgent = useMemo(
    () => ({
      fisher: fisherRunsQ.data ?? [],
      scenario: scenarioRunsQ.data ?? [],
      redflag: redflagRunsQ.data ?? [],
      tournament: tournamentRunsQ.data ?? [],
    }),
    [fisherRunsQ.data, scenarioRunsQ.data, redflagRunsQ.data, tournamentRunsQ.data]
  );

  const allRunsLoaded =
    !fisherRunsQ.isLoading &&
    !scenarioRunsQ.isLoading &&
    !redflagRunsQ.isLoading &&
    !tournamentRunsQ.isLoading;

  // Pick the agent with the most recent run (across all four) once data has
  // arrived, and expand exactly that section by default. Without runs we
  // fall back to the first one.
  const newestAgentId = useMemo<AgentId>(() => {
    let bestId: AgentId = AGENT_ORDER[0];
    let bestTs = "";
    for (const id of AGENT_ORDER) {
      const ts = runsByAgent[id][0]?.created_at;
      if (ts && ts > bestTs) {
        bestTs = ts;
        bestId = id;
      }
    }
    return bestId;
  }, [runsByAgent]);

  // Each section's expanded/collapsed state is independent so the user can
  // open multiple agents side-by-side. We seed the set with the agent that
  // has the most recent run, but every subsequent toggle is purely manual —
  // expanding one section never collapses another.
  const [expandedAgentIds, setExpandedAgentIds] = useState<Set<AgentId>>(
    () => new Set()
  );
  const initialised = useRef(false);
  useEffect(() => {
    if (initialised.current || !allRunsLoaded) return;
    initialised.current = true;
    // Deep-link via `?agent=…` always wins over the "newest run" heuristic,
    // so a click on a watchlist pill opens exactly the section the user
    // pointed at.
    setExpandedAgentIds(new Set([requestedAgent ?? newestAgentId]));
  }, [allRunsLoaded, newestAgentId, requestedAgent]);

  function toggleAgent(id: AgentId) {
    setExpandedAgentIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function expandAgent(id: AgentId) {
    setExpandedAgentIds((current) => {
      if (current.has(id)) return current;
      const next = new Set(current);
      next.add(id);
      return next;
    });
  }

  const agentInfoById = useMemo<Partial<Record<AgentId, AgentInfo>>>(() => {
    const out: Partial<Record<AgentId, AgentInfo>> = {};
    for (const a of agentsQuery.data ?? []) {
      if ((AGENT_ORDER as readonly string[]).includes(a.id)) {
        out[a.id as AgentId] = a;
      }
    }
    return out;
  }, [agentsQuery.data]);

  const showSpinner = agentsQuery.isLoading || !allRunsLoaded;

  return (
    <section className="detail-card ai-panel">
      <div className="detail-card-head">
        <h3>KI-Analysen</h3>
        <span className="detail-card-hint">
          Läufe werden im Hintergrund ausgeführt — die jüngste Analyse ist
          automatisch geöffnet.
        </span>
      </div>
      {showSpinner && <Spinner label="Lade KI-Analysen …" />}
      {agentsQuery.isError && (
        <p className="form-banner-error">Agenten konnten nicht geladen werden.</p>
      )}
      {!showSpinner && agentsQuery.data && (
        <div className="ai-panel-stack">
          {AGENT_ORDER.map((id) => {
            const info = agentInfoById[id];
            if (!info) return null;
            return (
              <AgentSection
                key={id}
                agent={info}
                runs={runsByAgent[id]}
                isin={isin}
                currency={currency}
                isExpanded={expandedAgentIds.has(id)}
                onToggle={() => toggleAgent(id)}
                onExpand={() => expandAgent(id)}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}

export default AIAgentsPanel;
