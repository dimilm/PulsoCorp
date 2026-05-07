import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { WatchlistMobileCard } from "./WatchlistMobileCard";
import type { Stock } from "../../types";
import type { JobsTrendPoint } from "../../hooks/useJobsTrendsAggregate";

// Stub recharts ResizeObserver-dependent sparkline
vi.mock("../jobs/JobsSparkline", () => ({
  JobsSparkline: ({ points }: { points: JobsTrendPoint[] }) => (
    <div data-testid="sparkline-stub" data-points={points.length} />
  ),
}));

// Stub Dropdown / RowActionsMenu to avoid complex portal setup in tests
vi.mock("../RowActionsMenu", () => ({
  default: ({ stock }: { stock: Stock }) => (
    <button type="button" data-testid="row-actions" aria-label="Aktionen">
      {stock.name}
    </button>
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
    current_price: 120.5,
    day_change_pct: 2.3,
    last_updated: "2026-05-01T10:00:00",
    last_status: "ok",
    pe_forward: null,
    pe_min_5y: null,
    pe_max_5y: null,
    pe_avg_5y: null,
    dividend_yield_current: 3.5,
    dividend_yield_avg_5y: null,
    analyst_target_1y: null,
    analyst_target_distance_pct: 12.0,
    market_cap: null,
    equity_ratio: null,
    debt_ratio: null,
    revenue_growth: null,
    missing_metrics: [],
    invested_capital_eur: 0,
    tags: ["Tech", "Growth", "EU"],
    latest_ai_runs: {},
    ...overrides,
  };
}

const noop = async () => {};
const noopSync = () => {};

function renderCard(overrides: Partial<Stock> = {}, extra?: Partial<React.ComponentProps<typeof WatchlistMobileCard>>) {
  const stock = makeStock(overrides);
  return render(
    <MemoryRouter>
      <WatchlistMobileCard
        stock={stock}
        onRefresh={noop}
        onEdit={noopSync}
        onDelete={noop}
        {...extra}
      />
    </MemoryRouter>
  );
}

describe("WatchlistMobileCard", () => {
  it("renders stock name as a link", () => {
    renderCard();
    const link = screen.getByRole("link", { name: "Acme AG" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/stocks/DE0001");
  });

  it("renders ISIN and sector", () => {
    renderCard();
    expect(screen.getByText("DE0001")).toBeInTheDocument();
    // Sector appears in .wl-card-sector; use getAllByText because "Tech" also
    // appears as a tag pill
    const techEls = screen.getAllByText("Tech");
    expect(techEls.length).toBeGreaterThanOrEqual(1);
    const sectorEl = techEls.find((el) => el.classList.contains("wl-card-sector"));
    expect(sectorEl).toBeInTheDocument();
  });

  it("renders KPI labels", () => {
    renderCard();
    expect(screen.getByText("Kurs")).toBeInTheDocument();
    expect(screen.getByText("Tagesänd.")).toBeInTheDocument();
    expect(screen.getByText("Kursziel")).toBeInTheDocument();
  });

  it("renders tag pills (max 2 visible, overflow badge)", () => {
    renderCard();
    // "Tech" is both sector and tag — verify the tag pill is present
    const techPills = screen.getAllByText("Tech");
    const tagPill = techPills.find((el) => el.classList.contains("tag-pill"));
    expect(tagPill).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    // Third tag overflows into "+1"
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("renders Stellen row when jobsAggregate is provided", () => {
    renderCard({}, {
      jobsAggregate: { latest: 42, delta_7d: 5 },
    });
    expect(screen.getByText("Offene Stellen")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("+5 (7T)")).toBeInTheDocument();
  });

  it("renders sparkline when trendPoints are provided with >= 2 entries", () => {
    const points: JobsTrendPoint[] = [
      { date: "2026-04-01", count: 30 },
      { date: "2026-04-08", count: 35 },
      { date: "2026-04-15", count: 42 },
    ];
    renderCard({}, {
      jobsAggregate: { latest: 42, delta_7d: 7 },
      trendPoints: points,
    });
    expect(screen.getByTestId("sparkline-stub")).toBeInTheDocument();
    expect(screen.getByTestId("sparkline-stub")).toHaveAttribute("data-points", "3");
  });

  it("does not render Stellen row when no aggregate provided", () => {
    renderCard();
    expect(screen.queryByText("Offene Stellen")).not.toBeInTheDocument();
  });

  it("renders status badge when last_status is present", () => {
    renderCard({ last_status: "ok" });
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("renders actions kebab button", () => {
    renderCard();
    expect(screen.getByTestId("row-actions")).toBeInTheDocument();
  });
});
