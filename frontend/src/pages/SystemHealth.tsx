import { Cpu, Database, Server, ShieldCheck, Waves } from "lucide-react";
import { Badge } from "@/components/common/Badge";
import { Card } from "@/components/common/Card";
import { Spinner } from "@/components/common/Spinner";
import { useHealth } from "@/hooks/useHealth";
import { API_BASE_URL } from "@/lib/constants";

function statusTone(status: string | undefined) {
  if (!status) return "neutral" as const;
  const s = status.toLowerCase();
  if (s.includes("healthy") || s === "ready" || s === "active")
    return "allow" as const;
  if (s.includes("degraded") || s.includes("unreachable"))
    return "review" as const;
  if (s.includes("unhealthy") || s.includes("missing"))
    return "block" as const;
  return "neutral" as const;
}

export default function SystemHealth() {
  const { health, ollama, loading, error, refresh } = useHealth(true);

  return (
    <div className="space-y-4">
      <Card
        title="System Health"
        subtitle="Live probes against the local Agent ICE runtime"
        actions={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={refresh}
          >
            {loading ? <Spinner /> : null}
            Refresh
          </button>
        }
      >
        {error && (
          <div className="mb-3 rounded-lg border border-decision-block/40 bg-decision-block/10 px-3 py-2 text-xs text-decision-block">
            {error}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          <div className="panel-inset p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Server className="h-4 w-4 text-accent" />
              FastAPI backend
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone={statusTone(health?.api.status)}>
                {health?.api.status ?? "unknown"}
              </Badge>
              <span className="font-mono text-[11px] text-ink-secondary">
                {API_BASE_URL}
              </span>
            </div>
          </div>

          <div className="panel-inset p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Database className="h-4 w-4 text-accent" />
              SQLite
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone={statusTone(health?.database.status)}>
                {health?.database.status ?? "unknown"}
              </Badge>
              <span className="font-mono text-[11px] text-ink-secondary">
                {health?.database.path ?? "—"}
              </span>
            </div>
          </div>

          <div className="panel-inset p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <ShieldCheck className="h-4 w-4 text-accent" />
              Agent ICE
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone={statusTone(health?.ice.status)}>
                {health?.ice.status ?? "unknown"}
              </Badge>
              <Badge tone={health?.ice.fail_closed ? "allow" : "review"}>
                fail-closed: {health?.ice.fail_closed ? "on" : "off"}
              </Badge>
            </div>
          </div>

          <div className="panel-inset p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Waves className="h-4 w-4 text-accent" />
              Ollama endpoint
            </div>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone={statusTone(ollama?.status)}>
                {ollama?.status ?? "unknown"}
              </Badge>
              <span className="font-mono text-[11px] text-ink-secondary">
                {ollama?.base_url ?? "—"}
              </span>
            </div>
          </div>

          <div className="panel-inset p-4 md:col-span-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Cpu className="h-4 w-4 text-accent" />
              Qwen model
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={ollama?.model_installed ? "allow" : "block"}>
                {ollama?.model_installed ? "installed" : "not installed"}
              </Badge>
              <span className="font-mono text-[11px] text-ink-secondary">
                {ollama?.model ?? "—"}
              </span>
              {ollama?.detail && (
                <span className="text-[11px] text-ink-muted">
                  {ollama.detail}
                </span>
              )}
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}