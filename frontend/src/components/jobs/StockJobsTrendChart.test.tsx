import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useSearchParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StockJobsTrendChart } from "./StockJobsTrendChart";
import { api } from "../../api/client";
import type { StockJobsTrend } from "../../types/jobs";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn() },
}));

vi.mock("../../hooks/useChartTheme", () => ({
  useChartTheme: () => ({
    line: "#6366f1",
    grid: "#e5e7eb",
    tick: "#6b7280",
    tooltipBackground: "#fff",
    tooltipBorder: "#e5e7eb",
    tooltipText: "#111827",
  }),
}));

// Recharts uses ResizeObserver / SVG measurement; stub it out.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 400, height: 240 }}>{children}</div>
    ),
  };
});

const ISIN = "DE0007236101";

function makeWrapper(initialSearch = "") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[`/stocks/${ISIN}${initialSearch}`]}>
          <Routes>
            <Route path="/stocks/:isin" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

function makeTrend(points: { snapshot_date: string; jobs_count: number }[]): StockJobsTrend {
  return { isin: ISIN, days: 180, points };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("StockJobsTrendChart", () => {
  it("shows empty state when no points returned", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: makeTrend([]) });

    render(<StockJobsTrendChart isin={ISIN} />, { wrapper: makeWrapper() });

    expect(
      await screen.findByText(/Noch nicht genug Datenpunkte/i)
    ).toBeInTheDocument();
  });

  it("shows empty state with only one data point", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: makeTrend([{ snapshot_date: "2026-04-01", jobs_count: 42 }]),
    });

    render(<StockJobsTrendChart isin={ISIN} />, { wrapper: makeWrapper() });

    expect(
      await screen.findByText(/Noch nicht genug Datenpunkte/i)
    ).toBeInTheDocument();
  });

  it("renders chart when ≥2 data points are available", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: makeTrend([
        { snapshot_date: "2026-04-01", jobs_count: 100 },
        { snapshot_date: "2026-04-15", jobs_count: 120 },
      ]),
    });

    render(<StockJobsTrendChart isin={ISIN} />, { wrapper: makeWrapper() });

    // The legend/source note mentions the count of data points.
    expect(await screen.findByText(/2 Messpunkte/i)).toBeInTheDocument();
  });

  it("range pills are rendered and default is 6M", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: makeTrend([]) });

    render(<StockJobsTrendChart isin={ISIN} />, { wrapper: makeWrapper() });

    await screen.findByText(/Noch nicht genug Datenpunkte/i);

    const sixM = screen.getByRole("tab", { name: "6M" });
    expect(sixM).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "1M" })).toHaveAttribute("aria-selected", "false");
  });

  it("clicking a range pill updates the URL search param", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: makeTrend([]) });
    const user = userEvent.setup();

    let capturedSearch = "";
    function CaptureSearch() {
      const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
      return (
        <QueryClientProvider client={qc}>
          <MemoryRouter initialEntries={[`/stocks/${ISIN}`]}>
            <Routes>
              <Route
                path="/stocks/:isin"
                element={
                  <>
                    <StockJobsTrendChart isin={ISIN} />
                    <SearchCapture onSearch={(s) => { capturedSearch = s; }} />
                  </>
                }
              />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      );
    }

    function SearchCapture({ onSearch }: { onSearch: (s: string) => void }) {
      const [p] = useSearchParams();
      onSearch(p.toString());
      return null;
    }

    render(<CaptureSearch />);
    await screen.findByText(/Noch nicht genug Datenpunkte/i);

    await user.click(screen.getByRole("tab", { name: "1M" }));

    expect(capturedSearch).toContain("jobs_range=1m");
  });
});
