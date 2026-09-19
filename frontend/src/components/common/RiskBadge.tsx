import { AlertOctagon, AlertTriangle, Info, ShieldAlert } from "lucide-react";
import type { RiskLevel } from "@/lib/constants";
import { Badge, type BadgeTone } from "./Badge";

const ICONS = {
  LOW: Info,
  MEDIUM: AlertTriangle,
  HIGH: ShieldAlert,
  CRITICAL: AlertOctagon,
} as const;

const TONES: Record<RiskLevel, BadgeTone> = {
  LOW: "low",
  MEDIUM: "medium",
  HIGH: "high",
  CRITICAL: "critical",
};

export function RiskBadge({
  level,
  score,
}: {
  level: RiskLevel;
  score?: number;
}) {
  const Icon = ICONS[level];
  return (
    <Badge tone={TONES[level]} title={`Risk: ${level}`}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{level}</span>
      {typeof score === "number" && (
        <span className="text-ink-secondary">· {score.toFixed(0)}</span>
      )}
    </Badge>
  );
}