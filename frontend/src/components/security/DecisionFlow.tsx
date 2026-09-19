import { ArrowDown } from "lucide-react";
import type { Decision } from "@/lib/constants";
import { DECISION_META } from "@/lib/constants";
import { cx } from "@/lib/utils";

export interface DecisionFlowProps {
  userIntent: string;
  agent: string;
  toolName: string;
  provenance: string;
  riskLevel: string;
  decision: Decision;
}

const NODE =
  "rounded-lg border border-line bg-base-inset px-3 py-2 text-center font-mono text-[11px] text-ink-secondary";

export function DecisionFlow({
  userIntent,
  agent,
  toolName,
  provenance,
  riskLevel,
  decision,
}: DecisionFlowProps) {
  const tone = DECISION_META[decision].tone;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className={cx(NODE, "w-full")}>USER: {userIntent}</div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div className={cx(NODE, "w-full")}>AGENT: {agent}</div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div className={cx(NODE, "w-full")}>TOOL REQUEST: {toolName}()</div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div className={cx(NODE, "w-full border-accent/40 text-accent")}>
        AGENT ICE
      </div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div className={cx(NODE, "w-full")}>PROVENANCE: {provenance}</div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div className={cx(NODE, "w-full")}>RISK: {riskLevel}</div>
      <ArrowDown className="h-3.5 w-3.5 text-ink-faint" aria-hidden="true" />
      <div
        className={cx(
          NODE,
          "w-full",
          tone === "allow" && "border-decision-allow/60 text-decision-allow",
          tone === "review" &&
            "border-decision-review/60 text-decision-review",
          tone === "restrict" &&
            "border-decision-restrict/60 text-decision-restrict",
          tone === "block" && "border-decision-block/60 text-decision-block",
        )}
      >
        DECISION: {decision}
      </div>
    </div>
  );
}