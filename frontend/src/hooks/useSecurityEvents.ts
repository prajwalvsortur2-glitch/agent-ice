import { useCallback, useEffect, useRef, useState } from "react";
import { listAuditEvents } from "@/api/audit";
import { POLL_INTERVAL_MS } from "@/lib/constants";
import type { AuditEvent } from "@/types";

export interface SecurityEventsState {
  events: AuditEvent[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  clear: () => void;
}

export function useSecurityEvents(
  sessionId?: string,
  poll = true,
): SecurityEventsState {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    try {
      const rows = await listAuditEvents({
        session_id: sessionId,
        limit: 200,
      });
      if (mounted.current) {
        setEvents(rows);
        setError(null);
      }
    } catch (err) {
      if (mounted.current) setError((err as Error).message);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    mounted.current = true;
    void load();
    if (!poll) {
      return () => {
        mounted.current = false;
      };
    }
    const id = window.setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [load, poll]);

  return {
    events,
    loading,
    error,
    refresh: load,
    clear: () => setEvents([]),
  };
}