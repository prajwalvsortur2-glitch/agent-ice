import { Activity, RefreshCw } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useHealth } from "@/hooks/useHealth";
import { ROUTES } from "@/lib/constants";
import { cx } from "@/lib/utils";
import { Spinner } from "@/components/common/Spinner";

const TITLES: Record<string, string> = {
  [ROUTES.overview]: "Overview",
  [ROUTES.liveMonitor]: "Live Monitor",
  [ROUTES.sessions]: "Agent Sessions",
  [ROUTES.incidents]: "Security Incidents",
  [ROUTES.provenance]: "Provenance",
  [ROUTES.policies]: "Policies",
  [ROUTES.audit]: "Audit Logs",
  [ROUTES.evaluation]: "Evaluation",
  [ROUTES.health]: "System Health",
};

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "h-2 w-2 rounded-full",
        ok ? "bg-decision-allow animate-pulse-soft" : "bg-decision-block",
      )}
    />
  );
}

export function Topbar() {
  const { pathname } = useLocation();
  const { health, ollama, loading, error, refresh } = useHealth(true);

  const apiOk = Boolean(health) && health!.status !== "unhealthy";
  const ollamaOk = Boolean(ollama) && ollama!.status === "ready";

  return (
    <header className="flex h-14 items-center justify-between gap-3 border-b border-line bg-base-panel/60 px-4">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold text-ink">
          {TITLES[pathname] ?? "Agent ICE"}
        </h1>
        <p className="truncate text-[11px] text-ink-muted">
          Intent-to-Action Security Controller · runtime enforcement
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div
          className="hidden items-center gap-2 rounded-lg border border-line bg-base-inset px-2.5 py-1.5 text-[11px] text-ink-secondary sm:flex"
          title="Backend health"
        >
          <StatusDot ok={apiOk} />
          <span className="font-mono">API {health?.status ?? "unknown"}</span>
        </div>
        <div
          className="hidden items-center gap-2 rounded-lg border border-line bg-base-inset px-2.5 py-1.5 text-[11px] text-ink-secondary sm:flex"
          title="Ollama / Qwen readiness"
        >
          <StatusDot ok={ollamaOk} />
          <span className="font-mono">
            {ollama ? `${ollama.model} · ${ollama.status}` : "ollama unknown"}
          </span>
        </div>

        <button
          type="button"
          onClick={refresh}
          className="btn btn-ghost btn-sm"
          aria-label="Refresh health"
        >
          {loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
        </button>

        <div className="hidden items-center gap-2 rounded-lg border border-line bg-base-inset px-2.5 py-1.5 text-[11px] text-ink-secondary lg:flex">
          <Activity className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
          <span className="font-mono">ICE ACTIVE</span>
        </div>
      </div>
      {error && (
        <span className="sr-only" role="alert">
          {error}
        </span>
      )}
    </header>
  );
}