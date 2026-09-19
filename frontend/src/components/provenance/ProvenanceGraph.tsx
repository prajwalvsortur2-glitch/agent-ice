import type { ProvenanceSource } from "@/types";
import { TrustBadge } from "@/components/common/TrustBadge";

export interface ProvenanceGraphProps {
  sources: ProvenanceSource[];
  finalDecision?: string;
}

export function ProvenanceGraph({
  sources,
  finalDecision,
}: ProvenanceGraphProps) {
  if (sources.length === 0) {
    return (
      <div className="panel-inset p-4 text-center text-xs text-ink-muted">
        No provenance recorded for this request.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="panel-inset p-3">
        <div className="text-[11px] uppercase tracking-wider text-ink-muted">
          Sources
        </div>
        <ul className="mt-2 space-y-1.5">
          {sources.map((s) => (
            <li
              key={`${s.source_id}:${s.source_type}`}
              className="flex flex-wrap items-center gap-2 text-xs"
            >
              <span className="font-mono text-ink">{s.source_id}</span>
              <span className="text-ink-muted">({s.source_type})</span>
              <TrustBadge level={s.trust_level} />
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col items-center gap-1 py-1 text-ink-faint">
        <span aria-hidden="true">│</span>
        <span aria-hidden="true">▼</span>
      </div>

      <div className="panel-inset p-3 text-center">
        <div className="text-[11px] uppercase tracking-wider text-ink-muted">
          Agent ICE
        </div>
        <div className="mt-1 font-mono text-xs text-accent">
          provenance aggregated → policy + risk
        </div>
      </div>

      {finalDecision && (
        <>
          <div className="flex flex-col items-center gap-1 py-1 text-ink-faint">
            <span aria-hidden="true">│</span>
            <span aria-hidden="true">▼</span>
          </div>
          <div className="panel-inset p-3 text-center font-mono text-xs text-ink">
            DECISION: {finalDecision}
          </div>
        </>
      )}
    </div>
  );
}