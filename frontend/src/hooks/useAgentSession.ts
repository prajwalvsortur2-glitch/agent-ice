import { useCallback, useEffect, useState } from "react";
import { createSession, getSession, listSessions } from "@/api/agent";
import type { Session } from "@/types";

const ACTIVE_SESSION_KEY = "agent-ice:active-session-id";

export interface AgentSessionState {
  sessions: Session[];
  activeSession: Session | null;
  loading: boolean;
  error: string | null;
  startSession: (userIntent: string) => Promise<Session>;
  selectSession: (sessionId: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useAgentSession(): AgentSessionState {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listSessions();
      setSessions(list);
      const stored = localStorage.getItem(ACTIVE_SESSION_KEY);
      if (stored) {
        const match = list.find((s) => s.session_id === stored);
        if (match) setActiveSession(match);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const startSession = useCallback(async (userIntent: string) => {
    setError(null);
    const created = await createSession({ user_intent: userIntent });
    setActiveSession(created);
    setSessions((prev) => [created, ...prev]);
    localStorage.setItem(ACTIVE_SESSION_KEY, created.session_id);
    return created;
  }, []);

  const selectSession = useCallback(async (sessionId: string) => {
    setError(null);
    const s = await getSession(sessionId);
    setActiveSession(s);
    localStorage.setItem(ACTIVE_SESSION_KEY, s.session_id);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    sessions,
    activeSession,
    loading,
    error,
    startSession,
    selectSession,
    refresh,
  };
}