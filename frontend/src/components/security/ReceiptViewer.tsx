import { Copy } from "lucide-react";
import { useState } from "react";
import { JsonViewer } from "@/components/common/JsonViewer";
import { shortHash } from "@/lib/formatters";
import type { ActionReceipt } from "@/types";

export function ReceiptViewer({ receipt }: { receipt: ActionReceipt }) {
  const [copied, setCopied] = useState(false);

  async function copySignature() {
    try {
      await navigator.clipboard.writeText(receipt.signature);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard access may be denied — convenience only */
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-[11px] text-ink-secondary">
          signature: {shortHash(receipt.signature, 12)}
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => void copySignature()}
          aria-label="Copy signature"
        >
          <Copy className="h-3.5 w-3.5" />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <JsonViewer value={receipt} maxHeight={240} />
      <p className="text-[10px] text-ink-muted">
        Verification is performed server-side by the executor. The frontend
        never trusts a receipt on its own.
      </p>
    </div>
  );
}