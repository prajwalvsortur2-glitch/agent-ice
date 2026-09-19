import { AlertOctagon, ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/common/Badge";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { JsonViewer } from "@/components/common/JsonViewer";
import { RiskBadge } from "@/components/common/RiskBadge";
import { ProvenanceGraph } from "@/components/provenance/ProvenanceGraph";
import {
  formatTimestamp,
  humanizeReasonCode,
  truncate,
} from "@/lib/formatters";
import type { Incident } from "@/types";

export function IncidentCard({ incident }: { incident: Incident }) {
  const [open, setOpen] = useState(false);

  return (
    <article className="panel animate-slide-in">
      <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <AlertOctagon
              className="h-4 w-4 text-decision-block"
              aria-hidden="true"
            />
            <span className="font-mono text-xs text-ink">
              {incident.incident_id}
            </span>
            <DecisionBadge decision={incident.decision} />
            <RiskBadge
              level={incident.risk_level}
              score={incident.risk_score}
            />
          </div>
          <div className="mt-1 truncate text-[11px] text-ink-secondary">
            {formatTimestamp(incident.timestamp)} · session{" "}
            <span className="font-mono">{incident.session_id}</span>
          </div>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          {open ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" /> Less
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" /> Details
            </>
          )}
        </button>
      </header>

      <div className="space-y-3 p-4">
        <div>
          <div className="label">User intent</div>
          <p className="text-xs text-ink-secondary">
            {truncate(incident.user_intent, 240)}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <div className="label">Tool</div>
            <div className="font-mono text-xs text-ink">
              {incident.tool_name}()
            </div>
          </div>
          <div>
            <div className="label">Arguments</div>
            <div className="font-mono text-xs text-ink-secondary">
              {truncate(incident.arguments_summary, 140)}
            </div>
          </div>
        </div>

        <div>
          <div className="label">Why was this blocked?</div>
          <p className="text-xs text-ink-secondary">{incident.why_blocked}</p>
        </div>

        {incident.reason_codes.length > 0 && (
          <div>
            <div className="label">Reason codes</div>
            <ul className="flex flex-wrap gap-1.5">
              {incident.reason_codes.map((c) => (
                <li key={c} className="chip border-line bg-base-elevated">
                  {humanizeReasonCode(c)}
                </li>
              ))}
            </ul>
          </div>
        )}

        {incident.matched_rules.length > 0 && (
          <div>
            <div className="label">Triggered rules</div>
            <ul className="flex flex-wrap gap-1.5">
              {incident.matched_rules.map((r) => (
                <li key={r} className="chip border-line bg-base-elevated">
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {open && (
          <>
            <div>
              <div className="label">Provenance</div>
              <ProvenanceGraph sources={incident.provenance} />
            </div>

            {incident.deep_analysis && (
              <div>
                <div className="label">Qwen contextual analysis</div>
                <JsonViewer value={incident.deep_analysis} maxHeight={200} />
              </div>
            )}

            {incident.containment && (
              <div>
                <div className="label">Containment</div>
                <div className="panel-inset p-3 text-xs">
                  <div className="font-mono">
                    {incident.containment.original_tool}() →{" "}
                    <span className="text-decision-restrict">
                      {incident.containment.restricted_tool}()
                    </span>
                  </div>
                  <div className="mt-1 text-ink-muted">
                    {incident.containment.reason}
                  </div>
                </div>
              </div>
            )}

            <div className="flex flex-wrap gap-1.5 pt-1">
              <Badge tone="neutral">
                session {incident.session_id.slice(0, 8)}…
              </Badge>
              <Badge tone="neutral">tool {incident.tool_name}</Badge>
            </div>
          </>
        )}
      </div>
    </article>
  );
}