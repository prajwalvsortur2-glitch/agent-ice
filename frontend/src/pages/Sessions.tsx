import { Activity, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { useAgentSession } from "@/hooks/useAgentSession";
import { ROUTES } from "@/lib/constants";
import { formatRelativeTime, shortHash, truncate } from "@/lib/formatters";

export default function Sessions() {
  const { sessions, activeSession, loading, selectSession, refresh } =
    useAgentSession();

  return (
    <div className="space-y-4">
      <Card
        title="Agent Sessions"
        subtitle={`${sessions.length} total · active: ${activeSession?.session_id?.slice(0, 8) ?? "none"}`}
        actions={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void refresh()}
          >
            {loading ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </button>
        }
        bodyClassName="p-0"
      >
        {sessions.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No sessions yet"
            description="Start a session from the Live Monitor."
            action={
              <Link to={ROUTES.liveMonitor} className="btn btn-primary btn-sm">
                Open Live Monitor
              </Link>
            }
          />
        ) : (
          <ul className="divide-y divide-line">
            {sessions.map((s) => {
              const isActive = activeSession?.session_id === s.session_id;
              return (
                <li
                  key={s.session_id}
                  className={
                    "flex flex-col gap-2 px-4 py-3 md:flex-row md:items-center md:justify-between " +
                    (isActive ? "bg-accent/5" : "")
                  }
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-ink">
                        {shortHash(s.session_id, 8)}
                      </span>
                      {isActive && (
                        <span className="chip border-accent/40 bg-accent/10 text-accent">
                          active
                        </span>
                      )}
                      <span className="text-[10px] text-ink-muted">
                        {formatRelativeTime(s.created_at)}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-xs text-ink-secondary">
                      {truncate(s.user_intent, 160)}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-1.5 text-[10px] text-ink-muted">
                      <span className="font-mono">
                        intent_hash: {shortHash(s.intent_anchor.intent_hash, 8)}
                      </span>
                      <span>·</span>
                      <span>inspected {s.actions_inspected}</span>
                      <span>·</span>
                      <span>blocked {s.actions_blocked}</span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      className="btn btn-sm"
                      onClick={() => void selectSession(s.session_id)}
                    >
                      Select
                    </button>
                    <Link to={ROUTES.liveMonitor} className="btn btn-ghost btn-sm">
                      Open in Monitor
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}