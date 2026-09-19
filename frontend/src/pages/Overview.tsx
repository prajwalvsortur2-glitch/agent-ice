import {
  Activity,
  AlertOctagon,
  Ban,
  CheckCircle2,
  Radar,
  ShieldQuestion,
} from "lucide-react";
import { useMemo } from "react";
import { Card } from "@/components/common/Card";
import { StatCard } from "@/components/dashboard/StatCard";
import { DecisionDistribution } from "@/components/dashboard/DecisionDistribution";
import { RiskDistribution } from "@/components/dashboard/RiskDistribution";
import { RecentActivity } from "@/components/dashboard/RecentActivity";
import { useSecurityEvents } from "@/hooks/useSecurityEvents";
import { useHealth } from "@/hooks/useHealth";
import type { Decision, RiskLevel } from "@/lib/constants";

export default function Overview() {
  const { events, loading, error } = useSecurityEvents(undefined, true);
  const { health, ollama } = useHealth(true);

  const counts = useMemo(() => {
    const decision: Record<Decision, number> = {
      ALLOW: 0,
      REVIEW: 0,
      RESTRICT: 0,
      BLOCK: 0,
    };
    const risk: Record<RiskLevel, number> = {
      LOW: 0,
      MEDIUM: 0,
      HIGH: 0,
      CRITICAL: 0,
    };
    const sessions = new Set<string>();
    for (const e of events) {
      decision[e.decision] = (decision[e.decision] ?? 0) + 1;
      risk[e.risk_level] = (risk[e.risk_level] ?? 0) + 1;
      sessions.add(e.session_id);
    }
    return { decision, risk, sessions: sessions.size };
  }, [events]);

  return (
    <div className="space-y-4">
      <header className="panel relative overflow-hidden">
        <div
          className="grid-lines absolute inset-0 opacity-40"
          aria-hidden="true"
        />
        <div className="relative p-5">
          <div className="flex items-center gap-2 text-accent">
            <Radar className="h-4 w-4" aria-hidden="true" />
            <span className="text-[11px] font-medium uppercase tracking-widest">
              Agent ICE · Security Operations
            </span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink">
            Intent-to-Action Security Controller
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-ink-secondary">
            Real-time runtime enforcement between the AI agent and its tools.
            The agent proposes. ICE authorizes. A signed receipt binds the exact
            action. The executor enforces.
          </p>

          <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-ink-secondary">
            <span className="chip border-line bg-base-inset">
              API {health?.status ?? "unknown"}
            </span>
            <span className="chip border-line bg-base-inset">
              Ollama {ollama?.status ?? "unknown"}
            </span>
            <span className="chip border-accent/40 bg-accent/10 text-accent">
              fail-closed: {health?.ice.fail_closed ? "on" : "off"}
            </span>
          </div>
        </div>
      </header>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <StatCard
          label="Active Sessions"
          value={counts.sessions}
          icon={Activity}
          tone="accent"
          loading={loading}
        />
        <StatCard
          label="Actions Inspected"
          value={events.length}
          icon={ShieldQuestion}
          loading={loading}
        />
        <StatCard
          label="Allowed"
          value={counts.decision.ALLOW}
          icon={CheckCircle2}
          tone="allow"
          loading={loading}
        />
        <StatCard
          label="Review"
          value={counts.decision.REVIEW}
          icon={Activity}
          tone="review"
          loading={loading}
        />
        <StatCard
          label="Restricted"
          value={counts.decision.RESTRICT}
          icon={Ban}
          tone="restrict"
          loading={loading}
        />
        <StatCard
          label="Blocked"
          value={counts.decision.BLOCK}
          icon={AlertOctagon}
          tone="block"
          loading={loading}
        />
      </section>

      {error && (
        <div className="panel border-decision-block/40 bg-decision-block/5 p-3 text-xs text-decision-block">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Decision distribution" subtitle="Computed from audit events">
          <DecisionDistribution counts={counts.decision} />
        </Card>
        <Card title="Risk distribution" subtitle="Computed from audit events">
          <RiskDistribution counts={counts.risk} />
        </Card>
        <Card
          title="System readiness"
          subtitle="Live health probes"
          bodyClassName="p-0"
        >
          <ul className="divide-y divide-line text-xs">
            <li className="flex items-center justify-between px-4 py-3">
              <span className="text-ink-secondary">FastAPI</span>
              <span className="font-mono text-ink">
                {health?.api.status ?? "unknown"}
              </span>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              <span className="text-ink-secondary">SQLite</span>
              <span className="font-mono text-ink">
                {health?.database.status ?? "unknown"}
              </span>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              <span className="text-ink-secondary">ICE</span>
              <span className="font-mono text-ink">
                {health?.ice.status ?? "unknown"}
              </span>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              <span className="text-ink-secondary">Ollama</span>
              <span className="font-mono text-ink">
                {ollama?.status ?? "unknown"}
              </span>
            </li>
            <li className="flex items-center justify-between px-4 py-3">
              <span className="text-ink-secondary">Qwen model</span>
              <span className="font-mono text-ink">
                {ollama?.model ?? "—"}
              </span>
            </li>
          </ul>
        </Card>
      </div>

      <Card
        title="Recent security events"
        subtitle="Newest first · read-only"
        bodyClassName="p-0"
      >
        <RecentActivity events={events} />
      </Card>
    </div>
  );
}