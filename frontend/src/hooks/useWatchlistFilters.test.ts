import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildStocksParams,
  emptyFilters,
  useWatchlistFilters,
} from "./useWatchlistFilters";

describe("buildStocksParams", () => {
  it("strips empty optional values", () => {
    const params = buildStocksParams(emptyFilters);
    expect(params.query).toBe("");
    expect(params.sector).toBeUndefined();
    expect(params.recommendation).toBeUndefined();
    expect(params.burggraben).toBeUndefined();
    expect(params.score_min).toBeUndefined();
    expect(params.score_max).toBeUndefined();
    expect(params.tags).toBeUndefined();
  });

  it("translates flags to backend params", () => {
    const params = buildStocksParams({
      ...emptyFilters,
      query: "abc",
      sector: "Tech",
      onlyBuy: true,
      onlyMoat: true,
      undervaluedDcf: true,
      undervaluedNav: true,
      scoreMin: 5,
      scoreMax: 9,
      tags: ["growth", "dividend"],
    });
    expect(params.query).toBe("abc");
    expect(params.sector).toBe("Tech");
    expect(params.recommendation).toBe("buy");
    expect(params.burggraben).toBe(true);
    expect(params.undervalued_dcf).toBe(true);
    expect(params.undervalued_nav).toBe(true);
    expect(params.score_min).toBe(5);
    expect(params.score_max).toBe(9);
    expect(params.tags).toBe("growth,dividend");
  });
});

describe("useWatchlistFilters", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("debounces value changes by 300ms", () => {
    const { result } = renderHook(() => useWatchlistFilters());

    act(() => {
      result.current.patch({ query: "a" });
    });
    expect(result.current.values.query).toBe("a");
    expect(result.current.debounced.query).toBe("");

    act(() => {
      vi.advanceTimersByTime(299);
    });
    expect(result.current.debounced.query).toBe("");

    act(() => {
      vi.advanceTimersByTime(2);
    });
    expect(result.current.debounced.query).toBe("a");
  });

  it("applyValues bypasses the debounce", () => {
    const { result } = renderHook(() => useWatchlistFilters());

    act(() => {
      result.current.applyValues({ ...emptyFilters, query: "instant" });
    });

    expect(result.current.values.query).toBe("instant");
    expect(result.current.debounced.query).toBe("instant");
  });

  it("toggleTag adds and removes tags", () => {
    const { result } = renderHook(() => useWatchlistFilters());

    act(() => {
      result.current.toggleTag("growth");
    });
    expect(result.current.values.tags).toEqual(["growth"]);

    act(() => {
      result.current.toggleTag("growth");
    });
    expect(result.current.values.tags).toEqual([]);
  });

  it("reset clears values without waiting for the debounce", () => {
    const { result } = renderHook(() => useWatchlistFilters());

    act(() => {
      result.current.patch({ query: "abc", onlyBuy: true });
    });
    act(() => {
      result.current.reset();
    });
    expect(result.current.values).toEqual(emptyFilters);
    expect(result.current.debounced).toEqual(emptyFilters);
  });
});
