import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { JobsMobileList } from "./JobsMobileList";
import type { JobSource, RunJobStatus } from "../../types/jobs";

function makeSource(overrides: Partial<JobSource> = {}): JobSource {
  return {
    id: 1,
    isin: "DE0001",
    name: "Acme Jobs",
    portal_url: "https://acme.de/jobs",
    adapter_type: "static_html",
    adapter_settings: {},
    is_active: true,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    latest_count: 42,
    latest_snapshot_date: "2026-05-01",
    delta_7d: 5,
    delta_30d: -3,
    ...overrides,
  };
}

const emptyStatusMap = new Map<number, RunJobStatus>();

describe("JobsMobileList", () => {
  it("renders empty state when no sources", () => {
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[]}
          statusByJobId={emptyStatusMap}
          isRunning={false}
          onRefreshSource={() => {}}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByText(/keine quellen/i)).toBeInTheDocument();
  });

  it("renders source name as a link", () => {
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[makeSource()]}
          statusByJobId={emptyStatusMap}
          isRunning={false}
          onRefreshSource={() => {}}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    const link = screen.getByRole("link", { name: "Acme Jobs" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/jobs/1");
  });

  it("renders latest count prominently", () => {
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[makeSource({ latest_count: 99 })]}
          statusByJobId={emptyStatusMap}
          isRunning={false}
          onRefreshSource={() => {}}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("99")).toBeInTheDocument();
  });

  it("renders delta badges", () => {
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[makeSource({ delta_7d: 5, delta_30d: -3 })]}
          statusByJobId={emptyStatusMap}
          isRunning={false}
          onRefreshSource={() => {}}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("+5")).toBeInTheDocument();
    expect(screen.getByText("-3")).toBeInTheDocument();
  });

  it("calls onRefreshSource when refresh button is clicked", () => {
    const onRefreshSource = vi.fn();
    const source = makeSource();
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[source]}
          statusByJobId={emptyStatusMap}
          isRunning={false}
          onRefreshSource={onRefreshSource}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole("button", { name: /refresh|aktualisieren/i }));
    expect(onRefreshSource).toHaveBeenCalledWith(source);
  });

  it("disables refresh button when isRunning is true and another row runs", () => {
    render(
      <MemoryRouter>
        <JobsMobileList
          sources={[makeSource()]}
          statusByJobId={emptyStatusMap}
          isRunning={true}
          onRefreshSource={() => {}}
          isRefreshPending={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByRole("button", { name: /refresh|aktualisieren/i })).toBeDisabled();
  });
});
