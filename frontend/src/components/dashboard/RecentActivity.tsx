import { Inbox } from "lucide-react";
import { Link } from "react-router-dom";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { RiskBadge } from "@/components/common/RiskBadge";
import { ROUTES } from "@/lib/constants";
import { formatRelativeTime, truncate } from "@/lib/formatters";
import type { AuditEvent } from "@/types";

export function RecentActivity({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="No security events yet"
        description="Start a session and issue a tool request to see decisions appear here."
        action={
          <Link to={ROUTES.liveMonitor} className="btn btn-primary btn-sm">
            Open Live Monitor
          </Link>
        }
      />
    );
  }

  return (
    <ul className="divide-y divide-line">
      {events.slice(0, 8).map((e) => (
        <li key={e.event_id} className="flex items-start gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-ink">
                {e.tool_name}()
              </span>
              <DecisionBadge decision={e.decision} />
              <RiskBadge level={e.risk_level} score={e.risk_score} />
            </div>
            <p className="mt-1 truncate text-[11px] text-ink-secondary">
              {truncate(e.user_intent, 120)}
            </p>
          </div>
          <span className="shrink-0 text-[10px] text-ink-muted">
            {formatRelativeTime(e.timestamp)}
          </span>
        </li>
      ))}
    </ul>
  );
}