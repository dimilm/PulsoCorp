import { describe, expect, it } from "vitest";

import {
  buildWatchlistUrl,
  parseWatchlistUrl,
  searchParamsEqual,
} from "./watchlistUrlState";

describe("parseWatchlistUrl", () => {
  it("returns defaults for an empty query string", () => {
    const state = parseWatchlistUrl(new URLSearchParams(""));
    expect(state.filters.query).toBe("");
    expect(state.filters.sector).toBe("");
    expect(state.filters.onlyMoat).toBe(false);
    expect(state.filters.tags).toEqual([]);
    expect(state.sortBy).toBe("name");
    expect(state.sortDir).toBe("asc");
  });

  it("decodes filters and sort", () => {
    const state = parseWatchlistUrl(
      new URLSearchParams("q=apple&sector=Tech&moat=1&tags=growth,ai&sortBy=score&sortDir=desc")
    );
    expect(state.filters.query).toBe("apple");
    expect(state.filters.sector).toBe("Tech");
    expect(state.filters.onlyMoat).toBe(true);
    expect(state.filters.tags).toEqual(["growth", "ai"]);
    expect(state.sortBy).toBe("score");
    expect(state.sortDir).toBe("desc");
  });

  it("ignores unknown sortDir values", () => {
    const state = parseWatchlistUrl(new URLSearchParams("sortDir=sideways"));
    expect(state.sortDir).toBe("asc");
  });
});

describe("buildWatchlistUrl", () => {
  it("strips defaults so the URL stays clean", () => {
    const params = buildWatchlistUrl({
      filters: { query: "", sector: "", onlyMoat: false, tags: [] },
      sortBy: "name",
      sortDir: "asc",
    });
    expect(params.toString()).toBe("");
  });

  it("encodes only set values", () => {
    const params = buildWatchlistUrl({
      filters: { query: "x", sector: "Tech", onlyMoat: true, tags: ["a", "b"] },
      sortBy: "score",
      sortDir: "desc",
    });
    expect(params.get("q")).toBe("x");
    expect(params.get("sector")).toBe("Tech");
    expect(params.get("moat")).toBe("1");
    expect(params.get("tags")).toBe("a,b");
    expect(params.get("sortBy")).toBe("score");
    expect(params.get("sortDir")).toBe("desc");
  });

  it("round-trips through parse", () => {
    const original = {
      filters: { query: "x", sector: "Tech", onlyMoat: true, tags: ["a", "b"] },
      sortBy: "score",
      sortDir: "desc" as const,
    };
    const params = buildWatchlistUrl(original);
    expect(parseWatchlistUrl(params)).toEqual(original);
  });
});

describe("searchParamsEqual", () => {
  it("returns true regardless of order", () => {
    const a = new URLSearchParams("q=x&sortBy=score");
    const b = new URLSearchParams("sortBy=score&q=x");
    expect(searchParamsEqual(a, b)).toBe(true);
  });

  it("returns false when values differ", () => {
    const a = new URLSearchParams("q=x");
    const b = new URLSearchParams("q=y");
    expect(searchParamsEqual(a, b)).toBe(false);
  });
});
