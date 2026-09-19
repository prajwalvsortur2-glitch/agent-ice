import { GitBranch } from "lucide-react";
import { useMemo, useState } from "react";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { ProvenanceGraph } from "@/components/provenance/ProvenanceGraph";
import { useSecurityEvents } from "@/hooks/useSecurityEvents";
import { formatRelativeTime, shortHash } from "@/lib/formatters";

export default function Provenance() {
  const { events } = useSecurityEvents(undefined, true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selected = useMemo(
    () => events.find((e) => e.event_id === selectedId) ?? events[0] ?? null,
    [events, selectedId],
  );

  if (events.length === 0) {
    return (
      <Card title="Provenance">
        <EmptyState
          icon={GitBranch}
          title="No provenance records"
          description="Provenance is attached to every tool request. Run an inspection to populate this view."
        />
      </Card>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card
        title="Events"
        subtitle={`${events.length} recent`}
        bodyClassName="p-0"
      >
        <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
          {events.map((e) => (
            <li key={e.event_id}>
              <button
                type="button"
                onClick={() => setSelectedId(e.event_id)}
                className={
                  "flex w-full items-start gap-3 px-4 py-2.5 text-left transition " +
                  (selected?.event_id === e.event_id
                    ? "bg-accent/5"
                    : "hover:bg-base-elevated")
                }
              >
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-xs text-ink">
                    {e.tool_name}()
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-ink-muted">
                    {shortHash(e.event_id, 6)} ·{" "}
                    {formatRelativeTime(e.timestamp)}
                  </div>
                </div>
                <span className="shrink-0 font-mono text-[11px] text-ink-secondary">
                  {e.provenance[0]?.trust_level ?? "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="Provenance graph"
        subtitle={selected ? `event ${shortHash(selected.event_id, 8)}` : ""}
      >
        {selected && (
          <div className="grid gap-4 md:grid-cols-2">
            <ProvenanceGraph
              sources={selected.provenance}
              finalDecision={selected.decision}
            />
            <div className="space-y-3">
              <div>
                <div className="label">Tool request</div>
                <div className="panel-inset p-3 font-mono text-xs text-ink-secondary">
                  {selected.tool_name}()
                </div>
              </div>
              <div>
                <div className="label">Raw event</div>
                <JsonViewer value={selected} maxHeight={360} />
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}