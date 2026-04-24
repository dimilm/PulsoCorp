import { useAgents } from "../../hooks/useAIAgents";
import { useStock } from "../../hooks/useStockQueries";
import { Spinner } from "../Spinner";
import { AgentCard } from "./AgentCard";

interface Props {
  isin: string;
}

export function AIAgentsPanel({ isin }: Props) {
  const agentsQuery = useAgents();
  const stockQuery = useStock(isin);
  const currency = stockQuery.data?.currency ?? null;

  return (
    <section className="detail-card ai-panel">
      <div className="detail-card-head">
        <h3>KI-Analysen</h3>
        <span className="detail-card-hint">
          Jede Analyse kann pro Unternehmen einzeln gestartet werden.
        </span>
      </div>
      {agentsQuery.isLoading && <Spinner label="Lade Agenten…" />}
      {agentsQuery.isError && (
        <p className="form-banner-error">Agenten konnten nicht geladen werden.</p>
      )}
      {agentsQuery.data && (
        <div className="ai-panel-grid">
          {agentsQuery.data.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              isin={isin}
              currency={currency}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export default AIAgentsPanel;
