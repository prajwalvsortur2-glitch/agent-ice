import { Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Card } from "@/components/common/Card";
import { DecisionBadge } from "@/components/common/DecisionBadge";
import { JsonViewer } from "@/components/common/JsonViewer";
import { RiskBadge } from "@/components/common/RiskBadge";
import { Spinner } from "@/components/common/Spinner";
import { DEMO_TOOLS, type DemoTool } from "@/lib/constants";
import { humanizeReasonCode, truncate } from "@/lib/formatters";
import type { InspectionResult, ProvenanceSource, TrustLevel } from "@/types";

const TRUST_OPTIONS: TrustLevel[] = ["TRUSTED", "RESTRICTED", "UNTRUSTED"];

export interface InspectConsoleProps {
  sessionId: string | null;
  onInspect: (payload: {
    session_id: string;
    tool_name: string;
    arguments: Record<string, unknown>;
    provenance: ProvenanceSource[];
  }) => Promise<InspectionResult>;
  onExecute: (result: InspectionResult) => Promise<void>;
  busy?: boolean;
}

export function InspectConsole({
  sessionId,
  onInspect,
  onExecute,
  busy = false,
}: InspectConsoleProps) {
  const [tool, setTool] = useState<DemoTool>("read_email");
  const [argsText, setArgsText] = useState<string>(
    JSON.stringify({ email_id: "email_001" }, null, 2),
  );
  const [provenanceText, setProvenanceText] = useState<string>(
    JSON.stringify(
      [
        {
          source_id: "user_prompt",
          source_type: "user",
          trust_level: "TRUSTED",
        },
      ],
      null,
      2,
    ),
  );
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InspectionResult | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!sessionId) {
      setError("Create a session first.");
      return;
    }
    setError(null);
    let parsedArgs: Record<string, unknown>;
    let parsedProv: ProvenanceSource[];
    try {
      parsedArgs = JSON.parse(argsText || "{}");
      parsedProv = JSON.parse(provenanceText || "[]");
      if (!Array.isArray(parsedProv))
        throw new Error("provenance must be an array");
      for (const p of parsedProv) {
        if (!TRUST_OPTIONS.includes(p.trust_level as TrustLevel)) {
          throw new Error(`invalid trust_level: ${String(p.trust_level)}`);
        }
      }
    } catch (err) {
      setError(`Invalid JSON: ${(err as Error).message}`);
      return;
    }
    try {
      const r = await onInspect({
        session_id: sessionId,
        tool_name: tool,
        arguments: parsedArgs,
        provenance: parsedProv,
      });
      setResult(r);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card
        title="Inspect Request"
        subtitle="POST /v1/inspect — evaluates, does not execute"
      >
        <form className="space-y-3" onSubmit={handleSubmit}>
          <div>
            <label className="label" htmlFor="tool-select">
              Tool
            </label>
            <select
              id="tool-select"
              className="input"
              value={tool}
              onChange={(e) => setTool(e.target.value as DemoTool)}
            >
              {DEMO_TOOLS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="label" htmlFor="args-input">
              Arguments (JSON)
            </label>
            <textarea
              id="args-input"
              className="input min-h-[140px] resize-y"
              spellCheck={false}
              value={argsText}
              onChange={(e) => setArgsText(e.target.value)}
            />
          </div>

          <div>
            <label className="label" htmlFor="prov-input">
              Provenance (JSON array)
            </label>
            <textarea
              id="prov-input"
              className="input min-h-[140px] resize-y"
              spellCheck={false}
              value={provenanceText}
              onChange={(e) => setProvenanceText(e.target.value)}
            />
          </div>

          {error && (
            <div
              role="alert"
              className="rounded-lg border border-decision-block/40 bg-decision-block/10 px-3 py-2 text-xs text-decision-block"
            >
              {error}
            </div>
          )}

          <div className="flex items-center justify-between gap-2">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={busy || !sessionId}
            >
              {busy ? <Spinner /> : <Play className="h-4 w-4" />}
              Run Inspection
            </button>
            {!sessionId && (
              <span className="text-[11px] text-ink-muted">
                No active session
              </span>
            )}
          </div>
        </form>
      </Card>

      <Card
        title="Inspection Result"
        subtitle={
          result
            ? `inspection ${result.inspection_id.slice(0, 8)}…`
            : "Run an inspection to see ICE's decision"
        }
      >
        {!result ? (
          <div className="grid place-items-center gap-2 py-8 text-center">
            <ShieldAlert
              className="h-6 w-6 text-ink-muted"
              aria-hidden="true"
            />
            <p className="text-xs text-ink-secondary">
              No inspection yet. The backend is the authority.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <DecisionBadge decision={result.decision} size="lg" />
              <RiskBadge level={result.risk_level} score={result.risk_score} />
            </div>

            {result.reason_codes.length > 0 && (
              <div>
                <div className="label">Reason codes</div>
                <ul className="flex flex-wrap gap-1.5">
                  {result.reason_codes.map((c) => (
                    <li key={c} className="chip border-line bg-base-elevated">
                      {humanizeReasonCode(c)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.matched_rules && result.matched_rules.length > 0 && (
              <div>
                <div className="label">Matched rules</div>
                <ul className="flex flex-wrap gap-1.5">
                  {result.matched_rules.map((r) => (
                    <li key={r} className="chip border-line bg-base-elevated">
                      {r}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.risk_components && (
              <div>
                <div className="label">Risk components</div>
                <JsonViewer value={result.risk_components} maxHeight={160} />
              </div>
            )}

            {result.containment && (
              <div>
                <div className="label">Containment</div>
                <div className="panel-inset p-3 text-xs text-ink-secondary">
                  <div className="font-mono">
                    {result.containment.original_tool}() →{" "}
                    <span className="text-decision-restrict">
                      {result.containment.restricted_tool}()
                    </span>
                  </div>
                  <div className="mt-1 text-ink-muted">
                    {truncate(result.containment.reason, 160)}
                  </div>
                </div>
              </div>
            )}

            {result.deep_analysis && (
              <div>
                <div className="label">
                  Deep analysis (Qwen — evidence only)
                </div>
                <JsonViewer value={result.deep_analysis} maxHeight={180} />
              </div>
            )}

            {result.receipt && (
              <div>
                <div className="label">
                  Action Receipt (issued by backend · bound to exact action)
                </div>
                <JsonViewer value={result.receipt} maxHeight={200} />
                <div className="mt-2 flex items-center justify-end">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    disabled={busy}
                    onClick={() => void onExecute(result)}
                  >
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Execute with Receipt
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}