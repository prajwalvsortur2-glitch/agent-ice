import { useCallback, useEffect, useRef, useState } from "react";
import { getHealth, getOllamaHealth } from "@/api/health";
import { POLL_INTERVAL_MS } from "@/lib/constants";
import type { HealthResponse, OllamaHealthResponse } from "@/types";

export interface HealthState {
  health: HealthResponse | null;
  ollama: OllamaHealthResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

export function useHealth(poll = true): HealthState {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ollama, setOllama] = useState<OllamaHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const [h, o] = await Promise.allSettled([getHealth(), getOllamaHealth()]);
      if (!mounted.current) return;
      if (h.status === "fulfilled") setHealth(h.value);
      else setHealth(null);
      if (o.status === "fulfilled") setOllama(o.value);
      else setOllama(null);
      setError(
        h.status === "rejected" && o.status === "rejected"
          ? "Backend unreachable"
          : null,
      );
    } catch (err) {
      if (mounted.current) setError((err as Error).message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    if (!poll) {
      return () => {
        mounted.current = false;
      };
    }
    const id = window.setInterval(() => void load(), POLL_INTERVAL_MS * 4);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [load, poll]);

  return { health, ollama, loading, error, refresh: () => void load() };
}