import { X } from "lucide-react";
import { useEffect, type ReactNode } from "react";
import { cx } from "@/lib/utils";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const width =
    size === "sm" ? "max-w-md" : size === "lg" ? "max-w-3xl" : "max-w-xl";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4 backdrop-blur-sm animate-slide-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={cx("panel w-full", width)}>
        <header className="panel-header">
          <div>
            <h3 id="modal-title" className="text-sm font-semibold text-ink">
              {title}
            </h3>
            {description && (
              <p className="mt-0.5 text-xs text-ink-secondary">{description}</p>
            )}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="max-h-[70vh] overflow-auto p-4">{children}</div>
        {footer && (
          <footer className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}