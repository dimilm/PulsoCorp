import { useEffect, useRef } from "react";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { RunSummary, StepStatus } from "../types/run";

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

// Subscribe to the global "current run" feed. Returns the latest snapshot and
// transparently polls (with backoff) while a run is hot. The query key is
// shared with RunsPage / RefreshStatusCard so multiple subscribers reuse the
// same network requests via React Query.
export function useCurrentRun() {
  const tickRef = useRef(0);
  const query = useQuery<RunSummary | null>({
    queryKey: ["run-current"],
    queryFn: async () => (await api.get("/run-logs/current")).data,
    refetchInterval: (q) => {
      const data = q.state.data as RunSummary | null | undefined;
      if (!data || data.phase === "finished") {
        tickRef.current = 0;
        return false;
      }
      const next = nextPollInterval(tickRef.current);
      tickRef.current += 1;
      return next;
    },
    placeholderData: keepPreviousData,
  });
  return query.data ?? null;
}

// Fire React Query invalidations the moment the global "current run" flips to
// `finished`. Use on pages that show derived data (stocks/dashboard) so they
// pick up fresh values right when a background refresh completes – without
// requiring the user to be on the Runs page.
export function useInvalidateOnRunFinish(queryKeys: readonly (readonly unknown[])[]) {
  const qc = useQueryClient();
  const current = useCurrentRun();
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
