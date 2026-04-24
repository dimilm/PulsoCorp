import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { AgentInfo, AIRun } from "../types";

export const AI_AGENTS_QUERY_KEY = ["ai", "agents"] as const;
export const AI_RUNS_QUERY_KEY = (agentId: string, isin: string) =>
  ["ai", "runs", agentId, isin] as const;
export const AI_PROMPT_QUERY_KEY = (agentId: string) => ["ai", "prompt", agentId] as const;

export function useAgents() {
  return useQuery<AgentInfo[]>({
    queryKey: AI_AGENTS_QUERY_KEY,
    queryFn: async () => (await api.get("/ai/agents")).data as AgentInfo[],
    staleTime: 10 * 60_000,
  });
}

export function useAgentPrompt(agentId: string | null) {
  return useQuery<string>({
    queryKey: AI_PROMPT_QUERY_KEY(agentId ?? ""),
    enabled: Boolean(agentId),
    queryFn: async () => {
      const res = await api.get(`/ai/agents/${agentId}/prompt`, {
        responseType: "text",
        transformResponse: [(d) => d as string],
      });
      return typeof res.data === "string" ? res.data : String(res.data);
    },
    staleTime: 60 * 60_000,
  });
}

export function useAgentRuns(agentId: string, isin: string | undefined, limit = 10) {
  return useQuery<AIRun[]>({
    queryKey: AI_RUNS_QUERY_KEY(agentId, isin ?? ""),
    enabled: Boolean(isin),
    queryFn: async () => {
      const res = await api.get(`/ai/agents/${agentId}/runs/${isin}`, {
        params: { limit },
      });
      return res.data as AIRun[];
    },
    staleTime: 30_000,
  });
}

export interface RunAgentParams {
  agentId: string;
  isin: string;
  peers?: string[];
}

export function useRunAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ agentId, isin, peers }: RunAgentParams): Promise<AIRun> => {
      const body: Record<string, unknown> = {};
      if (peers && peers.length > 0) body.peers = peers;
      const res = await api.post(`/ai/agents/${agentId}/run/${isin}`, body);
      return res.data as AIRun;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: AI_RUNS_QUERY_KEY(vars.agentId, vars.isin) });
    },
  });
}
