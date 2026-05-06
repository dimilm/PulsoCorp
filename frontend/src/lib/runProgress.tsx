import { createContext, ReactNode, useContext, useEffect, useRef } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import { parseBackendDate } from "./format";
import type { RunStockStatus, RunSummary, StepStatus } from "../types/run";

// Polling intervals in milliseconds. We start aggressively while the run is
// hot (every 1.5s) and back off for long-running jobs so we are not hitting
// the API hundreds of times. Capped at 8s so the UI still feels responsive.
export const POLL_INTERVALS_MS = [1500, 1500, 3000, 3000, 5000, 8000];

export function nextPollInterval(tickCount: number): number {
  const idx = Math.min(tickCount, POLL_INTERVALS_MS.length - 1);
  return POLL_INTERVALS_MS[idx];
}

export const STEP_STATUS_LABEL: Record<StepStatus, string> = {
  not_started: "wartet",
  running: "läuft",
  done: "fertig",
  error: "Fehler",
  cancelled: "abgebrochen",
};

export function phaseLabel(phase: string | null | undefined): string {
  switch (phase) {
    case "queued":
      return "Wird vorbereitet";
    case "running":
      return "Läuft";
    case "finished":
      return "Abgeschlossen";
    default:
      return phase ?? "-";
  }
}

export function runStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "ok":
      return "OK";
    case "skipped":
      return "Übersprungen";
    case "partial_error":
      return "Teilweise Fehler";
    case "error":
      return "Fehler";
    case "cancelled":
      return "Abgebrochen";
    default:
      return status ?? "-";
  }
}

// Live duration of a run in seconds, including in-flight runs that have no
// `duration_seconds` yet. Falls back to `Date.now()` so callers can render a
// growing "0:42" counter as long as a `setInterval` re-renders them.
export function liveRunSeconds(run: RunSummary): number {
  if (run.duration_seconds && run.phase === "finished") return run.duration_seconds;
  if (!run.started_at) return 0;
  const startedMs = parseBackendDate(run.started_at).getTime();
  if (Number.isNaN(startedMs)) return run.duration_seconds || 0;
  const endMs = run.finished_at ? parseBackendDate(run.finished_at).getTime() : Date.now();
  return Math.max(0, Math.round((endMs - startedMs) / 1000));
}

// Same idea but for an individual stock entry inside a run.
export function liveStockSeconds(s: RunStockStatus): number | null {
  if (!s.started_at) return null;
  const start = parseBackendDate(s.started_at).getTime();
  const end = s.finished_at ? parseBackendDate(s.finished_at).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.max(0, Math.round((end - start) / 1000));
}

export interface CurrentRunResult {
  data: RunSummary | null;
  isLoading: boolean;
  isFetching: boolean;
}

export type RunTypeFilter = "market" | "jobs" | "any";

// ---------------------------------------------------------------------------
// Context — single polling loop mounted once inside AuthProvider
// ---------------------------------------------------------------------------

const CurrentRunContext = createContext<CurrentRunResult | null>(null);

/** Mount once inside AuthProvider so every component reading `useCurrentRun`
 *  shares one polling loop instead of N separate intervals. */
export function CurrentRunProvider({ children }: { children: ReactNode }) {
  const result = useCurrentRunQuery("market", true);
  return (
    <CurrentRunContext.Provider value={result}>{children}</CurrentRunContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Internal query – shared by the Provider and the public hook fallback
// ---------------------------------------------------------------------------

function useCurrentRunQuery(runType: RunTypeFilter, enabled: boolean): CurrentRunResult {
  const tickRef = useRef(0);
  const query = useQuery<RunSummary | null>({
    queryKey: ["run-current", runType],
    enabled,
    queryFn: async () => {
      const params = runType === "any" ? {} : { run_type: runType };
      return (await api.get("/run-logs/current", { params })).data;
    },
    refetchInterval: enabled
      ? (q) => {
          const data = q.state.data as RunSummary | null | undefined;
          if (!data || data.phase === "finished") {
            tickRef.current = 0;
            return false;
          }
          const next = nextPollInterval(tickRef.current);
          tickRef.current += 1;
          return next;
        }
      : false,
    placeholderData: keepPreviousData,
  });
  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
  };
}

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

/** Subscribe to the "current run" feed.
 *
 * For `"market"` runs (the default) the data is served from `CurrentRunProvider`,
 * which maintains a single polling subscription for the whole app. Non-market
 * types fall back to their own direct query.
 */
export function useCurrentRun(runType: RunTypeFilter = "market"): CurrentRunResult {
  const ctx = useContext(CurrentRunContext);
  // Always call the query hook to satisfy the Rules of Hooks, but disable it
  // when the context already provides the data we need.
  const shouldUseDirect = !ctx || runType !== "market";
  const direct = useCurrentRunQuery(runType, shouldUseDirect);

  return shouldUseDirect ? direct : ctx;
}

// ---------------------------------------------------------------------------
// Invalidation helper
// ---------------------------------------------------------------------------

// Fire React Query invalidations the moment the global "current run" flips to
// `finished`. Use on pages that show derived data (stocks/dashboard) so they
// pick up fresh values right when a background refresh completes – without
// requiring the user to be on the Runs page.
export function useInvalidateOnRunFinish(queryKeys: readonly (readonly unknown[])[]) {
  const qc = useQueryClient();
  const { data: current } = useCurrentRun();
  const lastPhaseRef = useRef<string | null>(null);

  useEffect(() => {
    if (!current) return;
    if (lastPhaseRef.current !== "finished" && current.phase === "finished") {
      for (const key of queryKeys) {
        qc.invalidateQueries({ queryKey: key as unknown[] });
      }
    }
    lastPhaseRef.current = current.phase;
  }, [current, qc, queryKeys]);
}
