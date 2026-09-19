/**
 * Frontend constants.
 *
 * The frontend is NEVER the authority. These constants are used only for
 * display, routing, and fetch configuration. No security decision derives
 * from them.
 */

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export const POLL_INTERVAL_MS: number = Number(
  import.meta.env.VITE_POLL_INTERVAL_MS ?? 2500,
);

export const DECISIONS = ["ALLOW", "REVIEW", "RESTRICT", "BLOCK"] as const;
export type Decision = (typeof DECISIONS)[number];

export const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

export const TRUST_LEVELS = ["TRUSTED", "RESTRICTED", "UNTRUSTED"] as const;
export type TrustLevel = (typeof TRUST_LEVELS)[number];

export const DECISION_META: Record<
  Decision,
  { label: string; description: string; tone: string }
> = {
  ALLOW: {
    label: "Allowed",
    description: "Action is authorized and a signed receipt was issued.",
    tone: "allow",
  },
  REVIEW: {
    label: "Review",
    description: "Requires explicit user approval before execution.",
    tone: "review",
  },
  RESTRICT: {
    label: "Restricted",
    description: "Downgraded to a safer capability by the trusted executor.",
    tone: "restrict",
  },
  BLOCK: {
    label: "Blocked",
    description: "The tool must never execute for this request.",
    tone: "block",
  },
};

export const RISK_META: Record<
  RiskLevel,
  { label: string; tone: string; range: string }
> = {
  LOW: { label: "Low", tone: "low", range: "0 – 20" },
  MEDIUM: { label: "Medium", tone: "medium", range: "21 – 45" },
  HIGH: { label: "High", tone: "high", range: "46 – 70" },
  CRITICAL: { label: "Critical", tone: "critical", range: "71 – 100" },
};

export const DEMO_TOOLS = [
  "read_email",
  "read_file",
  "query_database",
  "send_email",
  "delete_record",
  "http_fetch",
] as const;
export type DemoTool = (typeof DEMO_TOOLS)[number];

export const ROUTES = {
  overview: "/",
  liveMonitor: "/live",
  sessions: "/sessions",
  incidents: "/incidents",
  provenance: "/provenance",
  policies: "/policies",
  audit: "/audit",
  evaluation: "/evaluation",
  health: "/health",
} as const;