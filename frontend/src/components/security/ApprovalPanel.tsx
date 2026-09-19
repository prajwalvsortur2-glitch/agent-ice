import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import type { InspectionResult } from "@/types";

export interface ApprovalPanelProps {
  result: InspectionResult;
  onDecision: (approve: boolean, note?: string) => Promise<void>;
  busy?: boolean;
}

export function ApprovalPanel({
  result,
  onDecision,
  busy = false,
}: ApprovalPanelProps) {
  const [note, setNote] = useState("");

  return (
    <div className="panel border-decision-review/40 bg-decision-review/5 p-4">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-decision-review">
          Step-up authorization required
        </span>
      </div>
      <p className="text-xs text-ink-secondary">
        This action is being held for explicit approval. Approval is bound to
        this exact <span className="font-mono">tool + arguments</span>. A
        different request must be approved separately.
      </p>

      <div className="panel-inset mt-3 p-3 font-mono text-[11px] text-ink-secondary">
        <div>tool: {result.tool_name}</div>
        <div className="mt-1 break-all">
          args_hash: {result.receipt?.arguments_hash ?? "—"}
        </div>
      </div>

      <textarea
        className="input mt-3 min-h-[70px]"
        placeholder="Optional approver note (audit only)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />

      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          type="button"
          className="btn btn-danger btn-sm"
          disabled={busy}
          onClick={() => void onDecision(false, note)}
        >
          <XCircle className="h-3.5 w-3.5" /> Reject
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={busy}
          onClick={() => void onDecision(true, note)}
        >
          <CheckCircle2 className="h-3.5 w-3.5" /> Approve
        </button>
      </div>
    </div>
  );
}