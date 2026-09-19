import { ShieldCheck, ShieldHalf, ShieldX, UserCheck } from "lucide-react";
import type { Decision } from "@/lib/constants";
import { Badge, type BadgeTone } from "./Badge";

const ICONS = {
  ALLOW: ShieldCheck,
  REVIEW: UserCheck,
  RESTRICT: ShieldHalf,
  BLOCK: ShieldX,
} as const;

const TONES: Record<Decision, BadgeTone> = {
  ALLOW: "allow",
  REVIEW: "review",
  RESTRICT: "restrict",
  BLOCK: "block",
};

export function DecisionBadge({
  decision,
  size = "sm",
}: {
  decision: Decision;
  size?: "sm" | "md" | "lg";
}) {
  const Icon = ICONS[decision];
  const sizeCls =
    size === "lg"
      ? "px-3 py-1 text-sm"
      : size === "md"
        ? "px-2.5 py-0.5 text-xs"
        : "";
  return (
    <Badge tone={TONES[decision]} className={sizeCls} title={decision}>
      <Icon
        className={size === "lg" ? "h-4 w-4" : "h-3.5 w-3.5"}
        aria-hidden="true"
      />
      <span>{decision}</span>
    </Badge>
  );
}