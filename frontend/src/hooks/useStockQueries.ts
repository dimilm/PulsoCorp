import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { HistoryRange, HistoryResponse, Stock } from "../types";
import { STOCKS_QUERY_KEY, STOCKS_LIST_KEY } from "./useStockMutations";

export const SECTOR_SUGGESTIONS_KEY = [...STOCKS_QUERY_KEY, "sectors"] as const;

export interface SectorSuggestion {
  name: string;
  count: number;
}

export function useSectorSuggestions() {
  return useQuery<SectorSuggestion[]>({
    queryKey: SECTOR_SUGGESTIONS_KEY,
    queryFn: async () => {
      const res = await api.get("/stocks/sectors");
      return res.data as SectorSuggestion[];
    },
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
}

export const STOCK_DETAIL_KEY = (isin: string) => [...STOCKS_QUERY_KEY, "detail", isin] as const;
export const STOCK_HISTORY_KEY = (isin: string, range: HistoryRange) =>
  [...STOCKS_QUERY_KEY, "history", isin, range] as const;
export const STOCK_PEERS_KEY = (isin: string) => [...STOCKS_QUERY_KEY, "peers", isin] as const;

export function useStock(isin: string | undefined) {
  const queryClient = useQueryClient();
  return useQuery<Stock>({
    queryKey: STOCK_DETAIL_KEY(isin ?? ""),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/stocks/${isin}`);
      return res.data as Stock;
    },
    staleTime: 30_000,
    initialData: () => {
      if (!isin) return undefined;
      // Pull a possibly cached row from the watchlist list query so the page
      // can render instantly while the detail request is in flight.
      //
      // STOCKS_LIST_KEY is narrower than STOCKS_QUERY_KEY: it only matches the
      // paginated/filtered list caches (never detail, history, or peers), so
      // we don't need the Array.isArray guard any more.
      const cached = queryClient.getQueriesData<Stock[]>({ queryKey: STOCKS_LIST_KEY });
      for (const [, data] of cached) {
        if (!Array.isArray(data)) continue;
        const hit = (data as Stock[]).find((s) => s?.isin === isin);
        if (hit) return hit;
      }
      return undefined;
    },
  });
}

export function useStockHistory(isin: string | undefined, range: HistoryRange) {
  return useQuery<HistoryResponse>({
    queryKey: STOCK_HISTORY_KEY(isin ?? "", range),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/stocks/${isin}/history`, { params: { range } });
      return res.data as HistoryResponse;
    },
    // The backend itself caches per-interval; clients can be more relaxed.
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });
}

export function useStockPeers(isin: string | undefined, limit = 5) {
  return useQuery<Stock[]>({
    queryKey: STOCK_PEERS_KEY(isin ?? ""),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/stocks/${isin}/similar`, { params: { limit } });
      return res.data as Stock[];
    },
    staleTime: 60_000,
  });
}

/** Loads the full unfiltered watchlist. Uses the same STOCKS_LIST_KEY as
 *  WatchlistPage so cache entries are shared and prefix-invalidation via
 *  `invalidateQueries({ queryKey: STOCKS_LIST_KEY })` hits both. */
export function useStocks() {
  return useQuery<Stock[]>({
    queryKey: STOCKS_LIST_KEY,
    queryFn: async () => {
      const res = await api.get("/stocks");
      return res.data as Stock[];
    },
    staleTime: 60_000,
    gcTime: 10 * 60_000,
  });
}
