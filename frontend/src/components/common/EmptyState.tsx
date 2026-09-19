import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {Icon && (
        <div className="mb-1 grid h-10 w-10 place-items-center rounded-lg border border-line bg-base-elevated text-ink-muted">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      )}
      <h4 className="text-sm font-semibold text-ink">{title}</h4>
      {description && (
        <p className="max-w-sm text-xs text-ink-secondary">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}