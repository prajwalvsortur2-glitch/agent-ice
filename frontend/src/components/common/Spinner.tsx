import { Loader2 } from "lucide-react";
import { cx } from "@/lib/utils";

export function Spinner({
  className,
  label,
}: {
  className?: string;
  label?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cx(
        "inline-flex items-center gap-2 text-ink-secondary",
        className,
      )}
    >
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      {label && <span className="text-xs">{label}</span>}
      <span className="sr-only">Loading</span>
    </div>
  );
}