import { FileText, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { request } from "@/api/client";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { StatCard } from "@/components/dashboard/StatCard";
import type { EvaluationMetrics } from "@/types";
import { formatLatencyMs, formatTimestamp } from "@/lib/formatters";

export default function Evaluation() {
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const m = await request<EvaluationMetrics>("/v1/evaluation");
      setMetrics(m);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
      setMetrics(null);
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
        title="Evaluation"
        subtitle="Metrics are computed from actual attack + benign runs. Nothing is hard-coded."
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
            Run <span className="font-mono">python scripts/evaluate.py</span> to
            generate the results file. ({error})
          </div>
        )}
        {!metrics ? (
          <EmptyState
            icon={FileText}
            title="No evaluation results yet"
            description="Run scripts/evaluate.py against data/attacks and data/benign, then refresh."
          />
        ) : (
          <div className="space-y-4">
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Attack cases" value={metrics.attack_cases} />
              <StatCard
                label="Attacks blocked"
                value={metrics.blocked}
                tone="block"
              />
              <StatCard
                label="Attacks reviewed"
                value={metrics.reviewed}
                tone="review"
              />
              <StatCard
                label="Attacks restricted"
                value={metrics.restricted}
                tone="restrict"
              />
              <StatCard
                label="Attacks allowed (FN)"
                value={metrics.allowed_attacks}
                tone="block"
                hint="Lower is better"
              />
              <StatCard label="Benign cases" value={metrics.benign_cases} />
              <StatCard
                label="Benign allowed"
                value={metrics.benign_allowed}
                tone="allow"
              />
              <StatCard
                label="False positives"
                value={metrics.false_positives}
                hint="Benign blocked or restricted"
              />
            </section>

            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Legitimate success rate"
                value={`${(metrics.legitimate_task_success_rate * 100).toFixed(1)}%`}
                tone="allow"
              />
              <StatCard
                label="Avg latency"
                value={formatLatencyMs(metrics.average_latency_ms)}
              />
              <StatCard
                label="Median latency"
                value={formatLatencyMs(metrics.median_latency_ms)}
              />
              <StatCard
                label="P95 latency"
                value={formatLatencyMs(metrics.p95_latency_ms)}
              />
              {typeof metrics.fast_path_latency_ms === "number" && (
                <StatCard
                  label="Fast-path latency"
                  value={formatLatencyMs(metrics.fast_path_latency_ms)}
                />
              )}
              {typeof metrics.deep_path_latency_ms === "number" && (
                <StatCard
                  label="Deep-path latency"
                  value={formatLatencyMs(metrics.deep_path_latency_ms)}
                />
              )}
            </section>

            <p className="text-[10px] text-ink-muted">
              Generated at {formatTimestamp(metrics.generated_at)}. These numbers
              are produced by scripts/evaluate.py from real executions.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}