import { RefreshCw, ScrollText, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Spinner } from "@/components/common/Spinner";
import { useSecurityEvents } from "@/hooks/useSecurityEvents";
import { DECISIONS, type Decision } from "@/lib/constants";
import {
  formatLatencyMs,
  formatTimestamp,
  humanizeReasonCode,
  shortHash,
} from "@/lib/formatters";

type Filter = "ALL" | Decision;

export default function Audit() {
  const { events, loading, refresh } = useSecurityEvents(undefined, true);
  const [query, setQuery] = useState("");
  const [decisionFilter, setDecisionFilter] = useState<Filter>("ALL");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      if (decisionFilter !== "ALL" && e.decision !== decisionFilter)
        return false;
      if (!q) return true;
      return (
        e.tool_name.toLowerCase().includes(q) ||
        e.session_id.toLowerCase().includes(q) ||
        e.user_intent.toLowerCase().includes(q) ||
        e.reason_codes.some((c) => c.toLowerCase().includes(q))
      );
    });
  }, [events, query, decisionFilter]);

  return (
    <div className="space-y-4">
      <Card
        title="Audit log"
        subtitle={`${filtered.length} of ${events.length} events`}
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
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-muted"
              aria-hidden="true"
            />
            <input
              className="input pl-9"
              placeholder="Filter by tool, session, intent, reason code…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setDecisionFilter("ALL")}
              className={
                "chip border-line bg-base-elevated " +
                (decisionFilter === "ALL"
                  ? "border-accent/60 text-accent"
                  : "")
              }
            >
              ALL
            </button>
            {DECISIONS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDecisionFilter(d)}
                className={
                  "chip border-line bg-base-elevated " +
                  (decisionFilter === d
                    ? "border-accent/60 text-accent"
                    : "")
                }
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <Card bodyClassName="p-0">
        {filtered.length === 0 ? (
          <EmptyState
            icon={ScrollText}
            title="No matching events"
            description="Adjust filters or run an inspection to generate events."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-left text-xs">
              <thead className="border-b border-line bg-base-inset text-[10px] uppercase tracking-wider text-ink-muted">
                <tr>
                  <th className="px-4 py-2">Time</th>
                  <th className="px-4 py-2">Session</th>
                  <th className="px-4 py-2">Tool</th>
                  <th className="px-4 py-2">Decision</th>
                  <th className="px-4 py-2">Risk</th>
                  <th className="px-4 py-2">Reasons</th>
                  <th className="px-4 py-2">Exec</th>
                  <th className="px-4 py-2">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filtered.map((e) => (
                  <tr key={e.event_id} className="hover:bg-base-elevated/60">
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-ink-secondary">
                      {formatTimestamp(e.timestamp)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-ink-secondary">
                      {shortHash(e.session_id, 6)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-ink">
                      {e.tool_name}
                    </td>
                    <td className="px-4 py-2">
                      <DecisionBadge decision={e.decision} />
                    </td>
                    <td className="px-4 py-2">
                      <RiskBadge level={e.risk_level} score={e.risk_score} />
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {e.reason_codes.slice(0, 3).map((c) => (
                          <Badge key={c} tone="neutral">
                            {humanizeReasonCode(c)}
                          </Badge>
                        ))}
                        {e.reason_codes.length > 3 && (
                          <Badge tone="neutral">
                            +{e.reason_codes.length - 3}
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-[11px] text-ink-secondary">
                      {e.execution_result ?? "—"}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-ink-secondary">
                      {typeof e.latency_ms === "number"
                        ? formatLatencyMs(e.latency_ms)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}