import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { Spinner } from "../components/Spinner";
import { Stock } from "../types";

interface DashboardData {
  total_stocks: number;
  total_invested_eur: number;
  portfolio_value_eur: number;
  portfolio_day_change_eur: number;
  portfolio_day_change_pct: number;
  moat_share_pct: number;
  last_run?: {
    started_at?: string;
    status?: string;
    stocks_success?: number;
    stocks_error?: number;
  } | null;
  winners?: Stock[];
  losers?: Stock[];
}

export function DashboardPage() {
  const { data } = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => (await api.get("/dashboard")).data,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  if (!data) {
    return (
      <div className="page">
        <Spinner label="Lade Dashboard..." />
      </div>
    );
  }
  return (
    <div className="page">
      <h2>Dashboard</h2>
      <p>Aktien gesamt: {data.total_stocks}</p>
      <p>Investiert: {Number(data.total_invested_eur ?? 0).toFixed(2)} EUR</p>
      <p>Depotwert (vereinfacht): {Number(data.portfolio_value_eur ?? 0).toFixed(2)} EUR</p>
      <p>
        Tagesveränderung: {Number(data.portfolio_day_change_eur ?? 0).toFixed(2)} EUR (
        {Number(data.portfolio_day_change_pct ?? 0).toFixed(2)} %)
      </p>
      <p>Burggraben-Anteil: {Number(data.moat_share_pct ?? 0).toFixed(2)} %</p>
      <p>
        Letzter Lauf: {data.last_run?.started_at ?? "-"} | Status: {data.last_run?.status ?? "-"} | ok{" "}
        {data.last_run?.stocks_success ?? 0} / err {data.last_run?.stocks_error ?? 0}
      </p>
      <h3>Top Gewinner</h3>
      <ul>
        {data.winners?.map((s) => (
          <li key={`w-${s.isin}`}>
            {s.name} ({Number(s.day_change_pct ?? 0).toFixed(2)} %)
          </li>
        ))}
      </ul>
      <h3>Top Verlierer</h3>
      <ul>
        {data.losers?.map((s) => (
          <li key={`l-${s.isin}`}>
            {s.name} ({Number(s.day_change_pct ?? 0).toFixed(2)} %)
          </li>
        ))}
      </ul>
    </div>
  );
}
