import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import WatchlistTable from "./WatchlistTable";
import type { Stock } from "../types";
import type { JobsTrendPoint } from "../hooks/useJobsTrendsAggregate";

// The real `JobsSparkline` uses `recharts` `<ResponsiveContainer>` which
// relies on `ResizeObserver` — not implemented by jsdom. We don't care
// about chart geometry here; we only assert that the cell decided to
// render a sparkline (vs. the fallback). A stub with a stable test id
// keeps the assertions tight.
vi.mock("./jobs/JobsSparkline", () => ({
  JobsSparkline: ({ points }: { points: JobsTrendPoint[] }) => (
    <div data-testid="jobs-sparkline-stub" data-points={points.length} />
  ),
}));

function makeStock(overrides: Partial<Stock> = {}): Stock {
  return {
    isin: "DE0001",
    name: "Acme AG",
    sector: "Tech",
    currency: "EUR",
    reasoning: null,
    tranches: 1,
    current_price: 100,
    day_change_pct: 1.2,
    last_updated: "2026-05-01T10:00:00",
    last_status: "ok",
    pe_forward: null,
    pe_min_5y: null,
    pe_max_5y: null,
    pe_avg_5y: null,
    dividend_yield_current: 2.5,
    dividend_yield_avg_5y: null,
    analyst_target_1y: null,
    market_cap: null,
    equity_ratio: null,
    debt_ratio: null,
    revenue_growth: null,
    missing_metrics: [],
    analyst_target_distance_pct: 5,
    invested_capital_eur: 0,
    tags: [],
    latest_ai_runs: {},
    ...overrides,
  };
}

const noop = () => {};
const asyncNoop = () => Promise.resolve();

function renderTable(props: Partial<Parameters<typeof WatchlistTable>[0]>) {
  return render(
    <MemoryRouter>
      <WatchlistTable
        stocks={[makeStock()]}
        sortBy="name"
        sortDir="asc"
        onSort={noop}
        onRefresh={asyncNoop}
        onEdit={noop}
        onDelete={asyncNoop}
        {...props}
      />
    </MemoryRouter>
  );
}

describe("WatchlistTable jobs sparkline cell", () => {
  it("always renders the Stellen column header (no toggle anymore)", () => {
    renderTable({});
    expect(screen.getByText("Stellen")).toBeInTheDocument();
    // No data yet -> the cell falls back to the dash placeholder.
    expect(screen.queryByTestId("jobs-sparkline-stub")).not.toBeInTheDocument();
  });

  it("renders the sparkline + latest count when ≥2 trend points exist", () => {
    renderTable({
      jobsByIsin: { DE0001: { latest: 42, delta_7d: 3 } },
      trendsByIsin: {
        DE0001: [
          { date: "2026-04-01", count: 30 },
          { date: "2026-04-15", count: 35 },
          { date: "2026-05-01", count: 42 },
        ],
      },
    });

    const sparkline = screen.getByTestId("jobs-sparkline-stub");
    expect(sparkline).toBeInTheDocument();
    expect(sparkline.dataset.points).toBe("3");

    // Tooltip surfaces latest, Δ7T and 90T min/max.
    const cell = sparkline.closest(".jobs-sparkline-cell") as HTMLElement;
    expect(cell).not.toBeNull();
    expect(cell.getAttribute("title")).toContain("Aktuell: 42");
    expect(cell.getAttribute("title")).toContain("Δ 7T: +3");
    expect(cell.getAttribute("title")).toContain("90T min/max: 30/42");

    // Latest count remains visible alongside the sparkline.
    expect(within(cell).getByText("42")).toBeInTheDocument();
    expect(within(cell).getByText(/\+3/)).toBeInTheDocument();
  });

  it("falls back to count + Δ when fewer than 2 trend points are available", () => {
    renderTable({
      jobsByIsin: { DE0001: { latest: 42, delta_7d: -2 } },
      trendsByIsin: { DE0001: [{ date: "2026-05-01", count: 42 }] },
    });

    expect(screen.queryByTestId("jobs-sparkline-stub")).not.toBeInTheDocument();
    // The cell must still surface the textual count + delta in this
    // degraded state so the column is never completely empty.
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText(/-2/)).toBeInTheDocument();
  });

  it("falls back to a dash when no aggregate is known for the row", () => {
    renderTable({
      jobsByIsin: { OTHER: { latest: 1, delta_7d: 0 } },
      trendsByIsin: {},
    });
    // Row's ISIN is not represented in the aggregate map: cell shows "-".
    // (The dash sits inside a <td> together with several other cells; we
    // assert via getAllByText since "-" repeats elsewhere on the row.)
    expect(screen.getAllByText("-").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("jobs-sparkline-stub")).not.toBeInTheDocument();
  });
});
