import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WatchlistFilterBar } from "./WatchlistFilterBar";
import { emptyFilters } from "../../hooks/useWatchlistFilters";
import type { ActiveFilter } from "./ActiveFilterChips";

const noop = () => {};

function makeProps(overrides: Partial<Parameters<typeof WatchlistFilterBar>[0]> = {}) {
  return {
    values: emptyFilters,
    onPatch: noop,
    filtersOpen: false,
    onToggleFilters: noop,
    activeFilters: [] as ActiveFilter[],
    presetNames: [],
    hasActiveFilters: false,
    onSavePreset: noop,
    onApplyPreset: noop,
    onDeletePreset: noop,
    ...overrides,
  };
}

describe("WatchlistFilterBar", () => {
  it("renders the search input", () => {
    render(<WatchlistFilterBar {...makeProps()} />);
    expect(screen.getByRole("textbox", { name: /suche/i })).toBeInTheDocument();
  });

  it("shows active filter badge count", () => {
    const activeFilters: ActiveFilter[] = [
      { key: "q", label: "Suche: foo", clear: noop },
      { key: "sector", label: "Sektor: Tech", clear: noop },
    ];
    render(<WatchlistFilterBar {...makeProps({ activeFilters })} />);
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("calls onToggleFilters when the Filter button is clicked", () => {
    const onToggleFilters = vi.fn();
    render(<WatchlistFilterBar {...makeProps({ onToggleFilters })} />);
    fireEvent.click(screen.getByRole("button", { name: /filter/i }));
    expect(onToggleFilters).toHaveBeenCalledOnce();
  });

  it("calls onPatch when search input changes", () => {
    const onPatch = vi.fn();
    render(<WatchlistFilterBar {...makeProps({ onPatch })} />);
    fireEvent.change(screen.getByRole("textbox", { name: /suche/i }), {
      target: { value: "test" },
    });
    expect(onPatch).toHaveBeenCalledWith({ query: "test" });
  });

  it("does not render a Stellen-Spalte toggle (column is always on)", () => {
    render(<WatchlistFilterBar {...makeProps()} />);
    expect(screen.queryByText(/Stellen-Spalte/)).not.toBeInTheDocument();
  });
});
