import { request } from "./client";
import type { HealthResponse, OllamaHealthResponse } from "@/types";

export async function getHealth(): Promise<HealthResponse> {
  const response = await request<{
    status: string;
    version: string;
    components: Record<string, string>;
    fail_closed: boolean;
  }>("/health", { timeoutMs: 5000 });

  return {
    status: response.status === "ok" ? "healthy" : "degraded",
    api: { status: response.status === "ok" ? "healthy" : response.status },
    database: { status: response.components.database ?? "unknown" },
    ice: {
      status: response.components.ice ?? "unknown",
      fail_closed: response.fail_closed,
    },
    timestamp: new Date().toISOString(),
    uptime_seconds: undefined,
  };
}

export async function getOllamaHealth(): Promise<OllamaHealthResponse> {
  const response = await request<{
    reachable: boolean;
    base_url: string;
    model: string;
    model_available: boolean;
    detail?: string | null;
  }>("/health/ollama", { timeoutMs: 8000 });

  return {
    status: !response.reachable
      ? "unreachable"
      : response.model_available
        ? "ready"
        : "model_missing",
    base_url: response.base_url,
    model: response.model,
    model_installed: response.model_available,
    detail: response.detail ?? undefined,
    timestamp: new Date().toISOString(),
  };
}