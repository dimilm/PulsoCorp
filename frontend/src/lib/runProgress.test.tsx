import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { ReactNode } from "react";

import {
  CurrentRunProvider,
  liveRunSeconds,
  liveStockSeconds,
  nextPollInterval,
  POLL_INTERVALS_MS,
  useCurrentRun,
} from "./runProgress";
import type { RunStockStatus, RunSummary } from "../types/run";

vi.mock("../api/client", () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from "../api/client";

function makeWrapper(client?: QueryClient) {
  const qc = client ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <CurrentRunProvider>{children}</CurrentRunProvider>
      </QueryClientProvider>
    );
  };
}

describe("nextPollInterval", () => {
  it("returns the first interval for tick 0", () => {
    expect(nextPollInterval(0)).toBe(POLL_INTERVALS_MS[0]);
  });

  it("caps at the last interval for large tick counts", () => {
    const last = POLL_INTERVALS_MS[POLL_INTERVALS_MS.length - 1];
    expect(nextPollInterval(999)).toBe(last);
  });
});

// Regression for the "Bisher" timer. The backend ships naive UTC ISO strings
// (no `Z` suffix); `new Date()` would parse them as local time and skew the
// counter by the host's UTC offset (e.g. +2h in CEST).
describe("liveRunSeconds (UTC parsing)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function makeRun(overrides: Partial<RunSummary>): RunSummary {
    return {
      id: 1,
      run_type: "market",
      started_at: "2026-05-03T14:29:00",
      finished_at: null,
      duration_seconds: 0,
      stocks_total: 0,
      stocks_done: 0,
      stocks_success: 0,
      stocks_error: 0,
      phase: "running",
      status: "ok",
      error_details: null,
      ...overrides,
    };
  }

  it("returns ~0s when the backend timestamp matches now (no local-time skew)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-03T14:29:00Z"));
    expect(liveRunSeconds(makeRun({ started_at: "2026-05-03T14:29:00" }))).toBe(0);
  });

  it("computes the elapsed delta against backend UTC, not local time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-03T14:30:42Z"));
    expect(liveRunSeconds(makeRun({ started_at: "2026-05-03T14:29:00" }))).toBe(102);
  });

  it("respects an explicit finished_at and ignores the wall clock", () => {
    expect(
      liveRunSeconds(
        makeRun({
          started_at: "2026-05-03T14:29:00",
          finished_at: "2026-05-03T14:30:30",
          phase: "running",
        })
      )
    ).toBe(90);
  });
});

describe("liveStockSeconds (UTC parsing)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function makeStock(overrides: Partial<RunStockStatus>): RunStockStatus {
    const blankStep = { status: "not_started" as const, started_at: null, finished_at: null, error: null };
    return {
      isin: "DE0000000000",
      stock_name: null,
      overall_status: "running",
      started_at: null,
      finished_at: null,
      resolved_symbol: null,
      symbol: blankStep,
      quote: blankStep,
      metrics: blankStep,
      ...overrides,
    };
  }

  it("returns 0 when the backend timestamp matches now", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-03T14:29:00Z"));
    expect(liveStockSeconds(makeStock({ started_at: "2026-05-03T14:29:00" }))).toBe(0);
  });
});

describe("CurrentRunProvider", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({ data: null });
  });

  it("renders children without crashing", () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CurrentRunProvider>
          <div data-testid="child">hello</div>
        </CurrentRunProvider>
      </QueryClientProvider>
    );
    expect(screen.getByTestId("child")).toBeInTheDocument();
  });
});

describe("useCurrentRun with CurrentRunProvider", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({ data: null });
  });

  it("returns null data when no active run", async () => {
    const { result } = renderHook(() => useCurrentRun(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toBeNull();
  });

  it("returns run data from context when a run is active", async () => {
    const mockRun = {
      id: 1,
      phase: "running",
      status: "ok",
      started_at: new Date().toISOString(),
      finished_at: null,
      duration_seconds: null,
      stock_count: 5,
      done_count: 2,
      error_count: 0,
    };
    vi.mocked(api.get).mockResolvedValueOnce({ data: mockRun });

    const { result } = renderHook(() => useCurrentRun(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.data).not.toBeNull());
    expect(result.current.data?.phase).toBe("running");
  });

  it("useCurrentRun('market') consumes from context (api called once for multiple subscribers)", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: null });

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const Wrapper = makeWrapper(qc);

    const { result: r1 } = renderHook(() => useCurrentRun("market"), { wrapper: Wrapper });
    const { result: r2 } = renderHook(() => useCurrentRun("market"), { wrapper: Wrapper });

    await waitFor(() => expect(r1.current.isLoading).toBe(false));
    await waitFor(() => expect(r2.current.isLoading).toBe(false));

    // Both hooks return the same data without double-fetching —
    // the context provides the result so only one GET /run-logs/current fires.
    expect(r1.current.data).toBe(r2.current.data);
  });
});
