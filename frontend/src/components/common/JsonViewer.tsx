import { prettyJson } from "@/lib/formatters";
import { cx } from "@/lib/utils";

export function JsonViewer({
  value,
  className,
  maxHeight = 320,
}: {
  value: unknown;
  className?: string;
  maxHeight?: number;
}) {
  return (
    <pre
      className={cx(
        "panel-inset overflow-auto p-3 font-mono text-[11px] leading-relaxed text-ink-secondary",
        className,
      )}
      style={{ maxHeight }}
    >
      {prettyJson(value)}
    </pre>
  );
}