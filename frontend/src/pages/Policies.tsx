import { RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Card } from "@/components/common/Card";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { EmptyState } from "@/components/common/EmptyState";
import { JsonViewer } from "@/components/common/JsonViewer";
import { Spinner } from "@/components/common/Spinner";
import { getPolicies } from "@/api/audit";
import { humanizeReasonCode } from "@/lib/formatters";
import type { PoliciesResponse } from "@/types";

export default function Policies() {
  const [policies, setPolicies] = useState<PoliciesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const p = await getPolicies();
      setPolicies(p);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="space-y-4">
      <Card
        title="Active policies"
        subtitle="Read-only view. Enforcement is server-side and deterministic."
        actions={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void load()}
          >
            {loading ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </button>
        }
      >
        {error && (
          <div className="mb-3 rounded-lg border border-decision-block/40 bg-decision-block/10 px-3 py-2 text-xs text-decision-block">
            {error}
          </div>
        )}

        {!policies ? (
          <EmptyState
            icon={ShieldCheck}
            title="No policies loaded"
            description="The backend exposes /v1/policies when the policy engine is initialised."
          />
        ) : (
          <div className="space-y-4">
            <div>
              <div className="label">Tool risk classes</div>
              <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
                {Object.entries(policies.tools).map(([tool, meta]) => (
                  <div key={tool} className="panel-inset p-3">
                    <div className="font-mono text-xs text-ink">{tool}</div>
                    <div className="mt-1 text-[11px] text-ink-secondary">
                      risk class: {meta.risk}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="label">Rules</div>
              <ul className="space-y-2">
                {policies.rules.map((r) => (
                  <li key={r.id} className="panel-inset p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-ink">{r.id}</span>
                      <DecisionBadge decision={r.decision} />
                      <span className="chip border-line bg-base-elevated">
                        {humanizeReasonCode(r.reason_code)}
                      </span>
                    </div>
                    <div className="mt-2">
                      <div className="label">when</div>
                      <JsonViewer value={r.when} maxHeight={140} />
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="label">Destination allowlist</div>
                <ul className="flex flex-wrap gap-1.5">
                  {policies.destinations.allowlist.map((d) => (
                    <li
                      key={d}
                      className="chip border-line bg-base-elevated font-mono"
                    >
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="label">Risk thresholds</div>
                <JsonViewer
                  value={policies.risk_thresholds}
                  maxHeight={140}
                />
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}