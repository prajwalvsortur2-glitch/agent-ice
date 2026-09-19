import type { ReactNode } from "react";
import { cx } from "@/lib/utils";

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  padded?: boolean;
}

export function Card({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  padded = true,
}: CardProps) {
  const hasHeader = Boolean(title || subtitle || actions);
  return (
    <section className={cx("panel overflow-hidden", className)}>
      {hasHeader && (
        <header className="panel-header">
          <div className="min-w-0">
            {title && (
              <h3 className="truncate text-sm font-semibold text-ink">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-0.5 truncate text-xs text-ink-secondary">
                {subtitle}
              </p>
            )}
          </div>
          {actions && (
            <div className="flex shrink-0 items-center gap-2">{actions}</div>
          )}
        </header>
      )}
      <div className={cx(padded && "p-4", bodyClassName)}>{children}</div>
    </section>
  );
}