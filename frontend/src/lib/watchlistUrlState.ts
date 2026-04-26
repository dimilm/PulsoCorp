import type { FilterValues } from "../hooks/useWatchlistFilters";
import { emptyFilters } from "../hooks/useWatchlistFilters";

export type SortDir = "asc" | "desc";

export interface WatchlistUrlState {
  filters: FilterValues;
  sortBy: string;
  sortDir: SortDir;
}

const PARAM_QUERY = "q";
const PARAM_SECTOR = "sector";
const PARAM_MOAT = "moat";
const PARAM_TAGS = "tags";
const PARAM_SORT_BY = "sortBy";
const PARAM_SORT_DIR = "sortDir";

const DEFAULT_SORT_BY = "name";
const DEFAULT_SORT_DIR: SortDir = "asc";

/** Decode the watchlist filter + sort state from a URLSearchParams instance.
 *
 * Unknown keys are ignored, missing keys fall back to defaults. The function
 * never throws so it stays safe for hand-edited URLs.
 */
export function parseWatchlistUrl(params: URLSearchParams): WatchlistUrlState {
  const tagsRaw = params.get(PARAM_TAGS);
  const tags = tagsRaw
    ? tagsRaw.split(",").map((t) => t.trim()).filter(Boolean)
    : [];
  const sortDirRaw = params.get(PARAM_SORT_DIR);
  return {
    filters: {
      ...emptyFilters,
      query: params.get(PARAM_QUERY) ?? "",
      sector: params.get(PARAM_SECTOR) ?? "",
      onlyMoat: params.get(PARAM_MOAT) === "1",
      tags,
    },
    sortBy: params.get(PARAM_SORT_BY) || DEFAULT_SORT_BY,
    sortDir: sortDirRaw === "desc" ? "desc" : "asc",
  };
}

/** Serialise the watchlist state into a URLSearchParams object.
 *
 * Default values are stripped so the URL stays clean ("/watchlist" instead of
 * "/watchlist?q=&moat=0&sortBy=name&sortDir=asc").
 */
export function buildWatchlistUrl(state: WatchlistUrlState): URLSearchParams {
  const next = new URLSearchParams();
  if (state.filters.query.trim()) next.set(PARAM_QUERY, state.filters.query.trim());
  if (state.filters.sector.trim()) next.set(PARAM_SECTOR, state.filters.sector.trim());
  if (state.filters.onlyMoat) next.set(PARAM_MOAT, "1");
  if (state.filters.tags.length > 0) next.set(PARAM_TAGS, state.filters.tags.join(","));
  if (state.sortBy && state.sortBy !== DEFAULT_SORT_BY) next.set(PARAM_SORT_BY, state.sortBy);
  if (state.sortDir !== DEFAULT_SORT_DIR) next.set(PARAM_SORT_DIR, state.sortDir);
  return next;
}

/** Compare two URLSearchParams as strings to skip redundant `setSearchParams`
 * calls (which would otherwise spam history entries). */
export function searchParamsEqual(a: URLSearchParams, b: URLSearchParams): boolean {
  // Sorting both sides keeps the comparison stable regardless of insertion
  // order.
  const aSorted = new URLSearchParams(a);
  aSorted.sort();
  const bSorted = new URLSearchParams(b);
  bSorted.sort();
  return aSorted.toString() === bSorted.toString();
}
