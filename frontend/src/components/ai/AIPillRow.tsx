import { Link } from "react-router-dom";

import type {
  AIAgentId,
  AILatestRun,
  FisherPillSummary,
  RedFlagPillSummary,
  ScenarioPillSummary,
  Stock,
  TournamentPillSummary,
} from "../../types";

interface Props {
  stock: Stock;
}

const AGENT_ORDER: AIAgentId[] = ["fisher", "redflag", "scenario", "tournament"];

const AGENT_LABEL: Record<AIAgentId, string> = {
  fisher: "Fisher",
  redflag: "Risiko",
  scenario: "Szenario",
  tournament: "Turnier",
};

const RISK_LABEL: Record<RedFlagPillSummary["overall_risk"], string> = {
  low: "Niedrig",
  med: "Mittel",
  high: "Hoch",
};

const VERDICT_LABEL: Record<FisherPillSummary["verdict"], string> = {
  strong: "Stark",
  neutral: "Neutral",
  weak: "Schwach",
};

// Formats "vor 3 Tagen" / "vor 5 Stunden" / "vor 2 Min." / "gerade eben". Used
// only for the tooltip — the pill itself stays compact, the timestamp lives
// in the title attribute.
function formatRelative(iso: string): string {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return iso;
  const diffMs = Date.now() - ts;
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes} Min.`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.round(hours / 24);
  if (days < 30) return `vor ${days} ${days === 1 ? "Tag" : "Tagen"}`;
  const months = Math.round(days / 30);
  return `vor ${months} ${months === 1 ? "Monat" : "Monaten"}`;
}

function tooltipFor(agentId: AIAgentId, run: AILatestRun): string {
  return `${AGENT_LABEL[agentId]} · ${formatRelative(run.created_at)} · ${run.model}`;
}

interface PillProps {
  agentId: AIAgentId;
  run: AILatestRun;
  isin: string;
  className: string;
  short: string;
  detail: string;
}

function AIPill({ agentId, run, isin, className, short, detail }: PillProps) {
  return (
    <Link
      to={`/stocks/${isin}?agent=${agentId}`}
      className={`ai-pill ${className}`}
      title={tooltipFor(agentId, run)}
      onClick={(e) => e.stopPropagation()}
    >
      <span className="ai-pill-short" aria-hidden="true">
        {short}
      </span>
      <span className="ai-pill-detail">{detail}</span>
    </Link>
  );
}

export function AIPillRow({ stock }: Props) {
  const runs = stock.latest_ai_runs ?? {};
  const pills: JSX.Element[] = [];

  for (const agentId of AGENT_ORDER) {
    const run = runs[agentId];
    if (!run) continue;
    const summary = run.summary as Record<string, unknown>;

    if (agentId === "fisher") {
      const s = summary as unknown as FisherPillSummary;
      pills.push(
        <AIPill
          key={agentId}
          agentId="fisher"
          run={run}
          isin={stock.isin}
          className={`ai-pill-fisher ai-pill-verdict-${s.verdict}`}
          short="F"
          detail={`${s.score}/30`}
        />
      );
    } else if (agentId === "redflag") {
      const s = summary as unknown as RedFlagPillSummary;
      pills.push(
        <AIPill
          key={agentId}
          agentId="redflag"
          run={run}
          isin={stock.isin}
          className={`ai-pill-risk ai-pill-risk-${s.overall_risk}`}
          short="R"
          detail={s.flag_count > 0 ? `${RISK_LABEL[s.overall_risk]} · ${s.flag_count}` : RISK_LABEL[s.overall_risk]}
        />
      );
    } else if (agentId === "scenario") {
      const s = summary as unknown as ScenarioPillSummary;
      const positive = s.expected_return_pct >= 0;
      const detail = `${positive ? "+" : ""}${s.expected_return_pct.toFixed(1)} %`;
      pills.push(
        <AIPill
          key={agentId}
          agentId="scenario"
          run={run}
          isin={stock.isin}
          className={`ai-pill-scenario ai-pill-scenario-${positive ? "pos" : "neg"}`}
          short="S"
          detail={detail}
        />
      );
    } else if (agentId === "tournament") {
      const s = summary as unknown as TournamentPillSummary;
      pills.push(
        <AIPill
          key={agentId}
          agentId="tournament"
          run={run}
          isin={stock.isin}
          className={`ai-pill-tournament ai-pill-tournament-${s.is_winner ? "winner" : "loser"}`}
          short="T"
          detail={s.is_winner ? "Sieger" : "Kein Sieg"}
        />
      );
    }
  }

  if (pills.length === 0) {
    return <span className="ai-pill-empty">–</span>;
  }
  // `verdict-strong` / `redflag-low` / etc. carry over their colour palette
  // from the existing detail-view styles via the pill class names below.
  // Tooltip is plain-text (`title`) for portability; if we ever need richer
  // tooltips we can layer them on top without touching consumers.
  return <span className="ai-pill-row">{pills}</span>;
}

export default AIPillRow;
