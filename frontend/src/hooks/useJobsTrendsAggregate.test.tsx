import { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useJobsTrendsAggregate } from "./useJobsTrendsAggregate";

vi.mock("../api/client", () => ({
  api: { get: vi.fn() },
}));

import { api } from "../api/client";

function wrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useJobsTrendsAggregate", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not fetch while disabled", async () => {
    renderHook(() => useJobsTrendsAggregate(false), { wrapper: wrapper() });
    // Give react-query a tick — `enabled: false` must stop the request
    // before it ever reaches the api client.
    await new Promise((r) => setTimeout(r, 10));
    expect(api.get).not.toHaveBeenCalled();
  });

  it("fetches and reshapes the wire format when enabled", async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        days: 90,
        items: [
          {
            isin: "DE0001",
            points: [
              { snapshot_date: "2026-04-01", jobs_count: 30 },
              { snapshot_date: "2026-04-15", jobs_count: 35 },
            ],
          },
          {
            isin: "DE0002",
            points: [{ snapshot_date: "2026-05-01", jobs_count: 7 }],
          },
        ],
      },
    });

    const { result } = renderHook(() => useJobsTrendsAggregate(true), {
      wrapper: wrapper(),
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(api.get).toHaveBeenCalledWith("/job-sources/trends", {
      params: { days: 90 },
    });

    const data = result.current.data!;
    expect(data.DE0001).toEqual([
      { date: "2026-04-01", count: 30 },
      { date: "2026-04-15", count: 35 },
    ]);
    expect(data.DE0002).toEqual([{ date: "2026-05-01", count: 7 }]);
  });

  it("forwards a custom days argument as a query parameter", async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { days: 30, items: [] } });

    const { result } = renderHook(() => useJobsTrendsAggregate(true, 30), {
      wrapper: wrapper(),
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(api.get).toHaveBeenCalledWith("/job-sources/trends", {
      params: { days: 30 },
    });
  });
});
