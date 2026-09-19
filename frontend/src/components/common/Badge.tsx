import type { ReactNode } from "react";
import { cx } from "@/lib/utils";

export type BadgeTone =
  | "neutral"
  | "accent"
  | "allow"
  | "review"
  | "restrict"
  | "block"
  | "low"
  | "medium"
  | "high"
  | "critical"
  | "trusted"
  | "restricted"
  | "untrusted";

const TONE_CLASS: Record<BadgeTone, string> = {
  neutral: "border-line bg-base-elevated text-ink-secondary",
  accent: "border-accent/40 bg-accent/10 text-accent",
  allow: "border-decision-allow/40 bg-decision-allow/10 text-decision-allow",
  review:
    "border-decision-review/40 bg-decision-review/10 text-decision-review",
  restrict:
    "border-decision-restrict/40 bg-decision-restrict/10 text-decision-restrict",
  block: "border-decision-block/40 bg-decision-block/10 text-decision-block",
  low: "border-risk-low/40 bg-risk-low/10 text-risk-low",
  medium: "border-risk-medium/40 bg-risk-medium/10 text-risk-medium",
  high: "border-risk-high/40 bg-risk-high/10 text-risk-high",
  critical: "border-risk-critical/40 bg-risk-critical/10 text-risk-critical",
  trusted: "border-trust-trusted/40 bg-trust-trusted/10 text-trust-trusted",
  restricted:
    "border-trust-restricted/40 bg-trust-restricted/10 text-trust-restricted",
  untrusted:
    "border-trust-untrusted/40 bg-trust-untrusted/10 text-trust-untrusted",
};

export interface BadgeProps {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
  title?: string;
}

export function Badge({
  tone = "neutral",
  children,
  className,
  title,
}: BadgeProps) {
  return (
    <span title={title} className={cx("chip", TONE_CLASS[tone], className)}>
      {children}
    </span>
  );
}