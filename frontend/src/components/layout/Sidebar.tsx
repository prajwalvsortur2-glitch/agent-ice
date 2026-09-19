import {
  Activity,
  AlertTriangle,
  FileText,
  GitBranch,
  LayoutDashboard,
  Radar,
  ScrollText,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { cx } from "@/lib/utils";
import { ROUTES } from "@/lib/constants";

const NAV = [
  { to: ROUTES.overview, label: "Overview", icon: LayoutDashboard },
  { to: ROUTES.liveMonitor, label: "Live Monitor", icon: Radar },
  { to: ROUTES.sessions, label: "Sessions", icon: Activity },
  { to: ROUTES.incidents, label: "Incidents", icon: AlertTriangle },
  { to: ROUTES.provenance, label: "Provenance", icon: GitBranch },
  { to: ROUTES.policies, label: "Policies", icon: ShieldCheck },
  { to: ROUTES.audit, label: "Audit Logs", icon: ScrollText },
  { to: ROUTES.evaluation, label: "Evaluation", icon: FileText },
  { to: ROUTES.health, label: "System Health", icon: TerminalSquare },
];

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-line bg-base-panel/60 md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-line px-4">
        <div className="grid h-7 w-7 place-items-center rounded-md border border-accent/40 bg-accent/10 text-accent">
          <ShieldCheck className="h-4 w-4" />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="truncate text-sm font-semibold text-ink">
            Agent ICE
          </div>
          <div className="truncate text-[10px] uppercase tracking-wider text-ink-muted">
            Security Console
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto p-2">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === ROUTES.overview}
            className={({ isActive }) =>
              cx(
                "group mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition",
                isActive
                  ? "bg-accent/10 text-accent shadow-glow"
                  : "text-ink-secondary hover:bg-base-elevated hover:text-ink",
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="truncate">{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-line p-3 text-[10px] leading-relaxed text-ink-muted">
        <div className="font-mono">runtime: local · qwen2.5:7b</div>
        <div className="mt-1">
          Frontend displays backend decisions only. No authorization here.
        </div>
      </div>
    </aside>
  );
}