import type { LucideIcon } from "lucide-react";
import { cx } from "@/lib/utils";

export interface StatCardProps {
  label: string;
  value: number | string;
  icon?: LucideIcon;
  tone?: "neutral" | "allow" | "review" | "restrict" | "block" | "accent";
  hint?: string;
  loading?: boolean;
}

const TONE_ICON: Record<NonNullable<StatCardProps["tone"]>, string> = {
  neutral: "text-ink-secondary border-line bg-base-elevated",
  accent: "text-accent border-accent/40 bg-accent/10",
  allow: "text-decision-allow border-decision-allow/40 bg-decision-allow/10",
  review:
    "text-decision-review border-decision-review/40 bg-decision-review/10",
  restrict:
    "text-decision-restrict border-decision-restrict/40 bg-decision-restrict/10",
  block: "text-decision-block border-decision-block/40 bg-decision-block/10",
};

export function StatCard({
  label,
  value,
  icon: Icon,
  tone = "neutral",
  hint,
  loading = false,
}: StatCardProps) {
  return (
    <div className="panel p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">
            {label}
          </div>
          <div
            className={cx(
              "mt-1 truncate font-mono text-2xl font-semibold text-ink",
              loading && "opacity-40",
            )}
          >
            {loading ? "—" : value}
          </div>
          {hint && (
            <div className="mt-1 truncate text-[11px] text-ink-secondary">
              {hint}
            </div>
          )}
        </div>
        {Icon && (
          <div
            className={cx(
              "grid h-9 w-9 shrink-0 place-items-center rounded-lg border",
              TONE_ICON[tone],
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
          </div>
        )}
      </div>
    </div>
  );
}