/**
 * Property-based tests for WatchlistTable — watchlist-jobs-column-split feature.
 *
 * Uses fast-check (fc) with Vitest. Each fc.assert block runs a minimum of
 * 100 iterations (fast-check default).
 *
 * Properties validated:
 *   Property 1 — Missing aggregate renders dashes in both cells
 *   Property 2 — Sufficient trend points render sparkline
 *   Property 3 — Insufficient trend points suppress sparkline
 *   Property 4 — Positive delta renders up-arrow
 *   Property 5 — Negative delta renders down-arrow
 *   Property 6 — Latest value always displayed
 *   Property 7 — Tooltip title contains correct aggregate data
 */

import { cleanup, render, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, vi } from "vitest";
import * as fc from "fast-check";

import WatchlistTable from "./WatchlistTable";
import type { Stock } from "../types";
import type { JobsTrendPoint } from "../hooks/useJobsTrendsAggregate";

// ---------------------------------------------------------------------------
// Mock — same as WatchlistTable.test.tsx
// ---------------------------------------------------------------------------

vi.mock("./jobs/JobsSparkline", () => ({
  JobsSparkline: ({ points }: { points: JobsTrendPoint[] }) => (
    <div data-testid="jobs-sparkline-stub" data-points={points.length} />
  ),
}));

// ---------------------------------------------------------------------------
// Helpers — copied from WatchlistTable.test.tsx (not imported to keep files
// independent and avoid coupling test files to each other)
// ---------------------------------------------------------------------------

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

function getTrendAndStellenCells(container: HTMLElement) {
  const headers = Array.from(container.querySelectorAll("thead th"));
  const trendIdx = headers.findIndex((th) => th.textContent === "Trend");
  const stellenIdx = headers.findIndex((th) => th.textContent === "Stellen");
  const cells = Array.from(container.querySelectorAll("tbody tr:first-child td"));
  return {
    trendCell: cells[trendIdx] as HTMLElement,
    stellenCell: cells[stellenIdx] as HTMLElement,
  };
}

// ---------------------------------------------------------------------------
// Arbitraries
// ---------------------------------------------------------------------------

// Use integer offsets from a fixed epoch to avoid fc.date() shrinking issues
// that can produce invalid Date objects in fast-check v4.
const MIN_DATE_MS = new Date("2025-01-01").getTime();
const MAX_DATE_MS = new Date("2026-12-31").getTime();

const trendPointArb = fc.record({
  date: fc
    .integer({ min: MIN_DATE_MS, max: MAX_DATE_MS })
    .map((ms) => new Date(ms).toISOString().slice(0, 10)),
  count: fc.integer({ min: 0, max: 10000 }),
});

// ---------------------------------------------------------------------------
// Cleanup after each test to avoid DOM accumulation
// ---------------------------------------------------------------------------

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Property tests
// ---------------------------------------------------------------------------

describe("WatchlistTable property-based tests", () => {
  /**
   * Property 1 — Missing aggregate data renders dashes in both cells
   *
   * For any stock whose ISIN is absent from jobsByIsin (or when jobsByIsin is
   * undefined), both the Trend cell and the Stellen cell SHALL render the dash
   * placeholder "–" and no JobsSparkline component SHALL be present in the DOM.
   *
   * Validates: Requirements 1.4, 5.1, 5.2
   */
  it("Property 1: missing aggregate renders dashes in both cells", () => {
    fc.assert(
      fc.property(
        // Generate a string that is guaranteed to differ from "DE0001"
        fc.string().filter((s) => s !== "DE0001"),
        (otherIsin) => {
          const { container } = renderTable({
            // jobsByIsin has an entry for a different ISIN — not for "DE0001"
            jobsByIsin: { [otherIsin]: { latest: 10, delta_7d: 0 } },
            trendsByIsin: {},
          });

          const { trendCell, stellenCell } = getTrendAndStellenCells(container);

          const trendOk = trendCell.textContent === "–";
          const stellenOk = stellenCell.textContent === "–";
          const noSparkline =
            container.querySelector('[data-testid="jobs-sparkline-stub"]') === null;

          cleanup();
          return trendOk && stellenOk && noSparkline;
        }
      )
    );
  });

  /**
   * Property 2 — Sufficient trend points render the sparkline
   *
   * For any stock with a valid JobsAggregate and an array of ≥ 2 JobsTrendPoint
   * values in trendsByIsin, the Trend cell SHALL render a JobsSparkline component
   * and the Stellen cell SHALL NOT contain a sparkline.
   *
   * Validates: Requirements 2.1
   */
  it("Property 2: sufficient trend points render the sparkline", () => {
    fc.assert(
      fc.property(
        fc.array(trendPointArb, { minLength: 2 }),
        (trendPoints) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest: 10, delta_7d: 0 } },
            trendsByIsin: { DE0001: trendPoints },
          });

          const { trendCell, stellenCell } = getTrendAndStellenCells(container);

          const sparklineInTrend =
            within(trendCell).queryByTestId("jobs-sparkline-stub") !== null;
          const noSparklineInStellen =
            within(stellenCell).queryByTestId("jobs-sparkline-stub") === null;

          cleanup();
          return sparklineInTrend && noSparklineInStellen;
        }
      )
    );
  });

  /**
   * Property 3 — Insufficient trend points suppress the sparkline
   *
   * For any stock with a valid JobsAggregate and fewer than 2 JobsTrendPoint
   * values (including zero), the Trend cell SHALL render "–" and no JobsSparkline
   * component SHALL appear anywhere in the row.
   *
   * Validates: Requirements 2.2, 2.3
   */
  it("Property 3: insufficient trend points suppress the sparkline", () => {
    fc.assert(
      fc.property(
        fc.array(trendPointArb, { maxLength: 1 }),
        (trendPoints) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest: 10, delta_7d: 0 } },
            trendsByIsin: { DE0001: trendPoints },
          });

          const { trendCell } = getTrendAndStellenCells(container);

          const trendIsDash = trendCell.textContent === "–";
          const noSparkline =
            container.querySelector('[data-testid="jobs-sparkline-stub"]') === null;

          cleanup();
          return trendIsDash && noSparkline;
        }
      )
    );
  });

  /**
   * Property 4 — Positive delta renders an up-arrow with delta-up class
   *
   * For any stock where JobsAggregate.latest is a non-null number and delta_7d
   * is a positive integer, the Stellen cell SHALL contain a <span> with CSS class
   * delta-up whose text content is "↑".
   *
   * Validates: Requirements 3.3, 4.1
   */
  it("Property 4: positive delta renders up-arrow with delta-up class", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1 }),   // delta_7d > 0
        fc.integer({ min: 0 }),   // latest >= 0
        (delta, latest) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest, delta_7d: delta } },
          });

          const { stellenCell } = getTrendAndStellenCells(container);

          const arrow = stellenCell.querySelector(".delta-up");
          const hasUpArrow = arrow !== null && arrow.textContent === "↑";
          const noDownArrow = stellenCell.querySelector(".delta-down") === null;

          cleanup();
          return hasUpArrow && noDownArrow;
        }
      )
    );
  });

  /**
   * Property 5 — Negative delta renders a down-arrow with delta-down class
   *
   * For any stock where JobsAggregate.latest is a non-null number and delta_7d
   * is a negative integer, the Stellen cell SHALL contain a <span> with CSS class
   * delta-down whose text content is "↓".
   *
   * Validates: Requirements 3.4, 4.1
   */
  it("Property 5: negative delta renders down-arrow with delta-down class", () => {
    fc.assert(
      fc.property(
        fc.integer({ max: -1 }),  // delta_7d < 0
        fc.integer({ min: 0 }),   // latest >= 0
        (delta, latest) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest, delta_7d: delta } },
          });

          const { stellenCell } = getTrendAndStellenCells(container);

          const arrow = stellenCell.querySelector(".delta-down");
          const hasDownArrow = arrow !== null && arrow.textContent === "↓";
          const noUpArrow = stellenCell.querySelector(".delta-up") === null;

          cleanup();
          return hasDownArrow && noUpArrow;
        }
      )
    );
  });

  /**
   * Property 6 — Latest value is always displayed in the Stellen cell
   *
   * For any stock where JobsAggregate.latest is a non-null number, the Stellen
   * cell SHALL display that exact numeric value as visible text, regardless of
   * the value of delta_7d or the number of trend points available.
   *
   * Validates: Requirements 3.1
   */
  it("Property 6: latest value is always displayed in the Stellen cell", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0 }),          // latest >= 0
        fc.option(fc.integer()),         // delta_7d can be null or any integer
        (latest, delta) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest, delta_7d: delta } },
          });

          const { stellenCell } = getTrendAndStellenCells(container);

          // The numeric value must appear somewhere in the cell's text content
          const cellText = stellenCell.textContent ?? "";
          const latestVisible = cellText.includes(String(latest));

          cleanup();
          return latestVisible;
        }
      )
    );
  });

  /**
   * Property 7 — Tooltip title contains correct aggregate data
   *
   * For any stock with a non-null latest value, the jobs-sparkline-cell span's
   * title attribute SHALL contain "Aktuell: {latest}". When delta_7d is non-null
   * it SHALL also contain "Δ 7T: ". When ≥ 2 trend points are available it SHALL
   * also contain "90T min/max: ".
   *
   * Validates: Requirements 3.7
   */
  it("Property 7: tooltip title contains correct aggregate data", () => {
    fc.assert(
      fc.property(
        fc.record({
          latest: fc.integer({ min: 0 }),
          delta_7d: fc.option(fc.integer()),
        }),
        fc.array(trendPointArb),
        ({ latest, delta_7d }, trendPoints) => {
          const { container } = renderTable({
            jobsByIsin: { DE0001: { latest, delta_7d } },
            trendsByIsin: { DE0001: trendPoints },
          });

          const { stellenCell } = getTrendAndStellenCells(container);
          const tooltipSpan = stellenCell.querySelector(
            ".jobs-sparkline-cell"
          ) as HTMLElement | null;

          // The tooltip span must exist (latest is non-null)
          if (tooltipSpan === null) {
            cleanup();
            return false;
          }

          const title = tooltipSpan.getAttribute("title") ?? "";

          const hasAktuell = title.includes(`Aktuell: ${latest}`);
          const hasDelta = delta_7d == null ? true : title.includes("Δ 7T: ");
          const hasMinMax =
            trendPoints.length >= 2 ? title.includes("90T min/max: ") : true;

          cleanup();
          return hasAktuell && hasDelta && hasMinMax;
        }
      )
    );
  });
});
