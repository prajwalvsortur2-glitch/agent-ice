import { useState } from "react";
import { Ban, CheckCircle2, RefreshCw } from "lucide-react";
import { Card } from "@/components/common/Card";
import { EmptyState } from "@/components/common/EmptyState";
import { Spinner } from "@/components/common/Spinner";
import { ApprovalPanel } from "@/components/security/ApprovalPanel";
import { DecisionFlow } from "@/components/security/DecisionFlow";
import { InspectConsole } from "@/components/security/InspectConsole";
import { ReceiptViewer } from "@/components/security/ReceiptViewer";
import { approve, execute, inspect as apiInspect } from "@/api/ice";
import { useAgentSession } from "@/hooks/useAgentSession";
import { useSecurityEvents } from "@/hooks/useSecurityEvents";
import { humanizeReasonCode, truncate } from "@/lib/formatters";
import type { InspectionResult } from "@/types";

export default function LiveMonitor() {
  const { activeSession, sessions, startSession, selectSession } =
    useAgentSession();
  const { events, refresh: refreshEvents } = useSecurityEvents(
    activeSession?.session_id,
    true,
  );
  const [result, setResult] = useState<InspectionResult | null>(null);
  const [intentDraft, setIntentDraft] = useState(
    "Summarize my unread emails.",
  );
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  async function handleStart() {
    setBusy(true);
    try {
      await startSession(intentDraft.trim());
      await refreshEvents();
    } finally {
      setBusy(false);
    }
  }

  async function handleInspect(payload: {
    session_id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
    provenance: InspectionResult["provenance"];
  }) {
    setBusy(true);
    try {
      const r = await apiInspect(payload);
      setResult(r);
      await refreshEvents();
      return r;
    } finally {
      setBusy(false);
    }
  }

  async function handleExecute(r: InspectionResult) {
    if (!r.receipt || !activeSession) return;
    setBusy(true);
    try {
      const res = await execute({
        session_id: activeSession.session_id,
        tool_name: r.tool_name,
        arguments: r.arguments,
        receipt: r.receipt,
      });
      setFlash(
        res.executed
          ? "Execution authorized by receipt."
          : `Execution denied: ${res.reason_code ?? res.error ?? "unknown"}`,
      );
      await refreshEvents();
    } finally {
      setBusy(false);
    }
  }

  async function handleApproval(approveFlag: boolean, note?: string) {
    if (!result || !activeSession) return;
    setBusy(true);
    try {
      const res = await approve({
        session_id: activeSession.session_id,
        inspection_id: result.inspection_id,
        approve: approveFlag,
        approver_note: note,
      });
      if (res.approved && res.receipt) {
        setResult({ ...result, receipt: res.receipt, decision: "ALLOW" });
        setFlash("Approved. Receipt issued. Execution is now permitted.");
      } else {
        setFlash("Rejected. Action will not execute.");
      }
      await refreshEvents();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card
        title="Session"
        subtitle={
          activeSession
            ? `session ${activeSession.session_id.slice(0, 10)}…`
            : "Create a session to begin"
        }
        actions={
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => void refreshEvents()}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        }
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto]">
          <div>
            <label className="label" htmlFor="intent-draft">
              User intent (becomes the immutable Intent Anchor)
            </label>
            <input
              id="intent-draft"
              className="input"
              value={intentDraft}
              onChange={(e) => setIntentDraft(e.target.value)}
            />
          </div>
          <div className="flex items-end gap-2">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void handleStart()}
              disabled={busy}
            >
              {busy ? <Spinner /> : <CheckCircle2 className="h-4 w-4" />}
              Start New Session
            </button>
          </div>
        </div>

        {sessions.length > 0 && (
          <div className="mt-3">
            <div className="label">Resume a session</div>
            <div className="flex flex-wrap gap-1.5">
              {sessions.slice(0, 6).map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  onClick={() => void selectSession(s.session_id)}
                  className={
                    "chip border-line bg-base-elevated hover:border-accent/40 " +
                    (activeSession?.session_id === s.session_id
                      ? "border-accent/60 text-accent"
                      : "")
                  }
                  title={s.user_intent}
                >
                  {s.session_id.slice(0, 8)}… · {truncate(s.user_intent, 30)}
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      {flash && (
        <div
          role="status"
          className="panel border-accent/40 bg-accent/5 px-4 py-2 text-xs text-accent"
        >
          {flash}
        </div>
      )}

      <InspectConsole
        sessionId={activeSession?.session_id ?? null}
        onInspect={handleInspect}
        onExecute={handleExecute}
        busy={busy}
      />

      {result?.decision === "REVIEW" && (
        <ApprovalPanel
          result={result}
          onDecision={handleApproval}
          busy={busy}
        />
      )}

      {result?.receipt && (
        <Card
          title="Action Receipt"
          subtitle="HMAC-SHA256 · bound to the exact tool + arguments"
        >
          <ReceiptViewer receipt={result.receipt} />
        </Card>
      )}

      {result && (
        <Card title="Flow" subtitle="Visualization of the current decision">
          <div className="mx-auto max-w-md">
            <DecisionFlow
              userIntent={truncate(activeSession?.user_intent ?? "—", 48)}
              agent="Qwen Agent"
              toolName={result.tool_name}
              provenance={result.provenance[0]?.trust_level ?? "TRUSTED"}
              riskLevel={result.risk_level}
              decision={result.decision}
            />
          </div>
        </Card>
      )}

      <Card
        title="Recent decisions in this session"
        subtitle="Server-side audit events"
        bodyClassName="p-0"
      >
        {events.length === 0 ? (
          <EmptyState
            icon={Ban}
            title="No events yet"
            description="Run an inspection to see ICE's decision appear here."
          />
        ) : (
          <ul className="divide-y divide-line">
            {events.slice(0, 12).map((e) => (
              <li
                key={e.event_id}
                className="flex items-center justify-between gap-3 px-4 py-2.5"
              >
                <div className="min-w-0">
                  <div className="font-mono text-xs text-ink">
                    {e.tool_name}()
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-ink-muted">
                    {e.reason_codes.map(humanizeReasonCode).join(" · ") ||
                      "no reason codes"}
                  </div>
                </div>
                <span className="shrink-0 font-mono text-[11px] text-ink-secondary">
                  {e.decision} · {e.risk_level}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}