import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { PlusIcon, SearchIcon } from "../components/icons";
import { Spinner } from "../components/Spinner";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import {
  formatCurrency,
  formatDateTime,
  formatPercent,
} from "../lib/format";
import { phaseLabel, runStatusLabel } from "../lib/runProgress";
import { Stock } from "../types";

interface DashboardData {
  total_stocks: number;
  total_invested_eur: number;
  portfolio_value_eur: number;
  portfolio_day_change_eur: number;
  portfolio_day_change_pct: number;
  last_run?: {
    id?: number | null;
    started_at?: string | null;
    finished_at?: string | null;
    phase?: string | null;
    status?: string | null;
    stocks_total?: number;
    stocks_done?: number;
    stocks_success?: number;
    stocks_error?: number;
  } | null;
  winners?: Stock[];
  losers?: Stock[];
}

interface KpiCardProps {
  label: string;
  value: string;
  hint?: string;
  delta?: { label: string; tone: "positive" | "negative" | "neutral" };
}

function KpiCard({ label, value, hint, delta }: KpiCardProps) {
  return (
    <div className="kpi-card">
      <div className="kpi-card-label">{label}</div>
      <div className="kpi-card-value">{value}</div>
      {delta && <div className={`kpi-card-delta kpi-card-delta-${delta.tone}`}>{delta.label}</div>}
      {hint && <div className="kpi-card-hint">{hint}</div>}
    </div>
  );
}

function changeTone(value: number): "positive" | "negative" | "neutral" {
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "neutral";
}

interface MoverRowProps {
  stock: Stock;
  scaleMax: number;
  variant: "winner" | "loser";
}

// Visual row with a horizontal bar that scales relative to the largest move
// in the same list, so the strongest mover always fills the bar.
function MoverRow({ stock, scaleMax, variant }: MoverRowProps) {
  const change = stock.day_change_pct ?? 0;
  const widthPct = scaleMax > 0 ? Math.min(100, Math.round((Math.abs(change) / scaleMax) * 100)) : 0;
  return (
    <li className={`mover-row mover-row-${variant}`}>
      <Link to={`/stocks/${stock.isin}`} className="mover-name">
        {stock.name}
      </Link>
      <div className="mover-bar">
        <div className={`mover-bar-fill mover-bar-${variant}`} style={{ width: `${widthPct}%` }} />
      </div>
      <span className={`mover-pct mover-pct-${variant}`}>{formatPercent(change)}</span>
    </li>
  );
}

function MoversList({
  title,
  stocks,
  variant,
  emptyHint,
}: {
  title: string;
  stocks: Stock[];
  variant: "winner" | "loser";
  emptyHint: string;
}) {
  const max = Math.max(0, ...stocks.map((s) => Math.abs(s.day_change_pct ?? 0)));
  return (
    <section className="mover-card">
      <header className="mover-card-head">
        <h3>{title}</h3>
        <span className="muted-count">{stocks.length}</span>
      </header>
      {stocks.length === 0 ? (
        <p className="mover-empty">{emptyHint}</p>
      ) : (
        <ol className="mover-list">
          {stocks.map((s) => (
            <MoverRow key={s.isin} stock={s} scaleMax={max} variant={variant} />
          ))}
        </ol>
      )}
    </section>
  );
}

function LastRunBanner({ lastRun }: { lastRun: NonNullable<DashboardData["last_run"]> }) {
  if (!lastRun.id) {
    return (
      <div className="dashboard-runline dashboard-runline-empty">
        Es wurde noch kein Marktdaten-Lauf ausgeführt.
      </div>
    );
  }
  const tone = lastRun.phase === "finished" && (lastRun.stocks_error ?? 0) === 0 ? "ok" : lastRun.stocks_error ? "warn" : "info";
  return (
    <div className={`dashboard-runline dashboard-runline-${tone}`}>
      <div>
        <strong>Letzter Lauf #{lastRun.id}</strong>
        <span> · {phaseLabel(lastRun.phase) ?? "–"}</span>
        {lastRun.status && <span> · {runStatusLabel(lastRun.status)}</span>}
      </div>
      <div className="dashboard-runline-meta">
        <span>{formatDateTime(lastRun.started_at)}</span>
        <span className="dashboard-runline-counts">
          OK {lastRun.stocks_success ?? 0} · Fehler {lastRun.stocks_error ?? 0} · Gesamt {lastRun.stocks_total ?? 0}
        </span>
        <Link to="/runs" className="dashboard-runline-link">
          Details
        </Link>
      </div>
    </div>
  );
}

export function DashboardPage() {
  useDocumentTitle("Dashboard");
  const { data, isLoading } = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard")).data,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  if (!data && isLoading) {
    return (
      <div className="page">
        <Spinner label="Lade Dashboard..." />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <h2>Dashboard</h2>
        <EmptyState
          icon={<SearchIcon size={20} />}
          title="Keine Daten verfügbar"
          description="Das Dashboard konnte nicht geladen werden. Versuche es später erneut."
        />
      </div>
    );
  }

  const totalStocks = data.total_stocks ?? 0;
  const dayChangeEur = Number(data.portfolio_day_change_eur ?? 0);
  const dayChangePct = Number(data.portfolio_day_change_pct ?? 0);
  const winners = data.winners ?? [];
  const losers = data.losers ?? [];

  if (totalStocks === 0) {
    return (
      <div className="page">
        <h2>Dashboard</h2>
        <EmptyState
          icon={<PlusIcon size={20} />}
          title="Willkommen bei CompanyTracker"
          description="Lege das erste Unternehmen in der Watchlist an, dann erscheinen hier KPIs, Top-Bewegungen und der Status des letzten Marktdaten-Laufs."
          action={
            <Link to="/watchlist" className="btn-primary">
              Zur Watchlist
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="page dashboard-page">
      <header className="page-header">
        <div className="page-header-title">
          <h2>Dashboard</h2>
        </div>
      </header>

      {data.last_run && <LastRunBanner lastRun={data.last_run} />}

      <section className="kpi-grid">
        <KpiCard
          label="Aktien gesamt"
          value={String(totalStocks)}
        />
        <KpiCard
          label="Investiertes Kapital"
          value={formatCurrency(data.total_invested_eur, "EUR")}
        />
        <KpiCard
          label="Depotwert"
          value={formatCurrency(data.portfolio_value_eur, "EUR")}
          delta={
            dayChangeEur !== 0
              ? {
                  label: `${dayChangeEur > 0 ? "+" : ""}${formatCurrency(dayChangeEur, "EUR")}`,
                  tone: changeTone(dayChangeEur),
                }
              : undefined
          }
        />
        <KpiCard
          label="Tagesveränderung"
          value={formatPercent(dayChangePct)}
          delta={{
            label: `${dayChangeEur > 0 ? "+" : ""}${formatCurrency(dayChangeEur, "EUR")}`,
            tone: changeTone(dayChangeEur),
          }}
        />
      </section>

      <section className="mover-grid">
        <MoversList
          title="Top Gewinner heute"
          stocks={winners}
          variant="winner"
          emptyHint="Keine Tagesgewinner."
        />
        <MoversList
          title="Top Verlierer heute"
          stocks={losers}
          variant="loser"
          emptyHint="Keine Tagesverlierer."
        />
      </section>
    </div>
  );
}
