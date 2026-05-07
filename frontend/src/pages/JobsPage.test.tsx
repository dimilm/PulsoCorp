import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { JobsPage } from "./JobsPage";
import { api } from "../api/client";
import type { JobSource, RunJobStatus } from "../types/jobs";
import type { RunSummary } from "../types/run";

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const baseSource: JobSource = {
  id: 1,
  isin: "DE0007236101",
  name: "Siemens Karriere",
  portal_url: "https://example.com/jobs",
  adapter_type: "json_get_path_int",
  adapter_settings: {},
  is_active: true,
  created_at: "2026-04-01T10:00:00",
  updated_at: "2026-05-01T10:00:00",
  latest_count: 42,
  latest_snapshot_date: "2026-05-02",
  delta_7d: 3,
  delta_30d: 8,
};

const otherSource: JobSource = {
  ...baseSource,
  id: 2,
  isin: "DE000BASF111",
  name: "BASF Karriere",
  latest_count: 17,
  delta_7d: -1,
  delta_30d: 0,
};

function makeRun(overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    id: 99,
    run_type: "jobs",
    started_at: "2026-05-03T17:00:00",
    finished_at: null,
    duration_seconds: 0,
    stocks_total: 2,
    stocks_done: 1,
    stocks_success: 1,
    stocks_error: 0,
    phase: "running",
    status: "ok",
    error_details: null,
    ...overrides,
  };
}

function makeStatus(overrides: Partial<RunJobStatus> & { job_source_id: number }): RunJobStatus {
  return {
    source_name: null,
    isin: null,
    overall_status: "not_started",
    started_at: null,
    finished_at: null,
    duration_ms: null,
    jobs_count: null,
    error: null,
    ...overrides,
  };
}

function buildResponder(
  routes: Record<string, unknown>,
  fallback: unknown = []
) {
  return async (url: string) => {
    for (const [pattern, payload] of Object.entries(routes)) {
      if (url === pattern || url.startsWith(`${pattern}?`)) {
        return { data: payload };
      }
    }
    return { data: fallback };
  };
}

function renderJobsPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={["/jobs"]}>
        <QueryClientProvider client={qc}>{children}</QueryClientProvider>
      </MemoryRouter>
    );
  }
  return render(<JobsPage />, { wrapper: Wrapper });
}

describe("JobsPage", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
    vi.mocked(api.post).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("hides the live summary card and live filter pills when no run is active", async () => {
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource, otherSource],
        "/run-logs/current": null,
      })
    );

    renderJobsPage();

    // Source rows must be visible once the list query resolves
    await waitFor(() =>
      expect(screen.getByText("Siemens Karriere")).toBeInTheDocument()
    );

    expect(screen.queryByText("Phase")).not.toBeInTheDocument();
    expect(screen.queryByText("Fortschritt")).not.toBeInTheDocument();
    // No live filter pill exists when no run is active. (The header's
    // "Alle aktualisieren" button reads "Alle aktualisieren" rather than
    // "Läuft…" in this state, so a "Läuft <count>"-style button must not
    // appear at all.)
    expect(screen.queryByRole("button", { name: /^Läuft \d+$/ })).not.toBeInTheDocument();

    // The Lauf-Status column header is always present, but the cell content
    // for each row falls back to the dash placeholder when no run rows exist.
    expect(screen.getByText("Lauf-Status")).toBeInTheDocument();
  });

  it("renders the summary card and live status badge when a run is active", async () => {
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource, otherSource],
        "/run-logs/current": makeRun(),
        "/run-logs/99/jobs": [
          makeStatus({
            job_source_id: 1,
            source_name: "Siemens Karriere",
            overall_status: "running",
            started_at: "2026-05-03T17:00:05",
          }),
          makeStatus({
            job_source_id: 2,
            source_name: "BASF Karriere",
            overall_status: "done",
            started_at: "2026-05-03T17:00:00",
            finished_at: "2026-05-03T17:00:04",
            jobs_count: 17,
          }),
        ],
      })
    );

    renderJobsPage();

    // Summary card fields
    await waitFor(() => expect(screen.getByText("Phase")).toBeInTheDocument());
    expect(screen.getByText("Fortschritt")).toBeInTheDocument();
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
    expect(screen.getByText(/Run #99/)).toBeInTheDocument();

    // Live filter pills appear. The pill's accessible name is "Läuft 1" /
    // "Fertig 1" because the count badge sits inside the same button — the
    // header's "Alle aktualisieren" button has the matching label "Läuft…"
    // when a run is in progress, hence the trailing-digit anchor.
    expect(screen.getByRole("button", { name: /^Läuft \d+$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Fertig \d+$/ })).toBeInTheDocument();

    // Per-row live status badges (uppercased by .run-badge css class — assert
    // the underlying lowercase label text from STEP_STATUS_LABEL)
    const badges = screen.getAllByText("läuft");
    expect(badges.length).toBeGreaterThan(0);
    expect(screen.getAllByText("fertig").length).toBeGreaterThan(0);

    // The currently running row is highlighted via run-row-running. The
    // Siemens row is the running one.
    const runningRowName = screen.getByText("Siemens Karriere");
    const runningRow = runningRowName.closest("tr");
    expect(runningRow).not.toBeNull();
    expect(runningRow?.className).toContain("run-row-running");
  });

  it("filters the table to only running rows when the Läuft pill is clicked", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource, otherSource],
        "/run-logs/current": makeRun(),
        "/run-logs/99/jobs": [
          makeStatus({
            job_source_id: 1,
            source_name: "Siemens Karriere",
            overall_status: "running",
            started_at: "2026-05-03T17:00:05",
          }),
          makeStatus({
            job_source_id: 2,
            source_name: "BASF Karriere",
            overall_status: "done",
            started_at: "2026-05-03T17:00:00",
            finished_at: "2026-05-03T17:00:04",
            jobs_count: 17,
          }),
        ],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("BASF Karriere")).toBeInTheDocument()
    );

    await user.click(screen.getByRole("button", { name: /^Läuft \d+$/ }));

    expect(screen.getByText("Siemens Karriere")).toBeInTheDocument();
    expect(screen.queryByText("BASF Karriere")).not.toBeInTheDocument();
  });

  // --- New tests for watchlist-add feature ---

  it("shows a watchlist-add button for ISINs not in the watchlist", async () => {
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource],
        "/run-logs/current": null,
        // stocks endpoint returns empty list → ISIN not in watchlist
        "/stocks": [],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("Siemens Karriere")).toBeInTheDocument()
    );

    // Should show a button with the ISIN (not a link)
    const addBtn = screen.getByRole("button", {
      name: new RegExp(`${baseSource.isin}.*zur Watchlist hinzufügen`, "i"),
    });
    expect(addBtn).toBeInTheDocument();
    expect(addBtn).not.toBeDisabled();
  });

  it("shows a link (not a button) for ISINs already in the watchlist", async () => {
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource],
        "/run-logs/current": null,
        // stocks endpoint returns the matching stock
        "/stocks": [
          {
            isin: baseSource.isin,
            name: "Siemens AG",
            sector: null,
            currency: null,
            reasoning: null,
            tranches: 0,
            current_price: null,
            day_change_pct: null,
            last_updated: null,
            last_status: null,
            pe_forward: null,
            pe_min_5y: null,
            pe_max_5y: null,
            pe_avg_5y: null,
            dividend_yield_current: null,
            dividend_yield_avg_5y: null,
            analyst_target_1y: null,
            market_cap: null,
            equity_ratio: null,
            debt_ratio: null,
            revenue_growth: null,
            missing_metrics: [],
            analyst_target_distance_pct: null,
            invested_capital_eur: 0,
            tags: [],
            latest_ai_runs: {},
          },
        ],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("Siemens Karriere")).toBeInTheDocument()
    );

    // Should show a link, not a watchlist-add button
    const isinLink = screen.getByRole("link", { name: baseSource.isin! });
    expect(isinLink).toBeInTheDocument();
    expect(isinLink).toHaveAttribute("href", `/stocks/${baseSource.isin}`);
    expect(
      screen.queryByRole("button", {
        name: new RegExp(`${baseSource.isin}.*zur Watchlist hinzufügen`, "i"),
      })
    ).not.toBeInTheDocument();
  });

  it("shows no button or link for sources without an ISIN", async () => {
    const noIsinSource: JobSource = { ...baseSource, id: 3, isin: null, name: "Kein ISIN" };
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [noIsinSource],
        "/run-logs/current": null,
        "/stocks": [],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("Kein ISIN")).toBeInTheDocument()
    );

    // The ISIN cell should show the dash placeholder — use getAllByText since
    // the Lauf-Status column also renders "–" for this row.
    const dashes = screen.getAllByText("–");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
    // No watchlist-add button
    expect(
      screen.queryByRole("button", { name: /zur Watchlist hinzufügen/i })
    ).not.toBeInTheDocument();
  });

  it("watchlist-add button remains clickable while a jobs refresh is running", async () => {
    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource],
        "/run-logs/current": makeRun(),
        "/run-logs/99/jobs": [],
        "/stocks": [],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("Siemens Karriere")).toBeInTheDocument()
    );

    const addBtn = screen.getByRole("button", {
      name: new RegExp(`${baseSource.isin}.*zur Watchlist hinzufügen`, "i"),
    });
    expect(addBtn).not.toBeDisabled();
  });

  it("opens the CreateStockModal with pre-filled values when the add button is clicked", async () => {
    const user = (await import("@testing-library/user-event")).default.setup();

    vi.mocked(api.get).mockImplementation(
      buildResponder({
        "/job-sources": [baseSource],
        "/run-logs/current": null,
        "/stocks": [],
      })
    );

    renderJobsPage();

    await waitFor(() =>
      expect(screen.getByText("Siemens Karriere")).toBeInTheDocument()
    );

    const addBtn = screen.getByRole("button", {
      name: new RegExp(`${baseSource.isin}.*zur Watchlist hinzufügen`, "i"),
    });
    await user.click(addBtn);

    // Modal should open
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // ISIN and name should be pre-filled
    expect((screen.getByLabelText(/isin/i) as HTMLInputElement).value).toBe(baseSource.isin);
    expect((screen.getByLabelText(/name/i) as HTMLInputElement).value).toBe(baseSource.name);
  });
});
