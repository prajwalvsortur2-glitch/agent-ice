import type { Decision, RiskLevel, TrustLevel } from "@/lib/constants";

export type { TrustLevel } from "@/lib/constants";

export interface ProvenanceSource {
  source_id: string;
  source_type: string;
  trust_level: TrustLevel;
}

export interface IntentAnchor {
  session_id: string;
  goal: string;
  allowed_tools: string[];
  allowed_operations: string[];
  restricted_operations: string[];
  intent_hash: string;
  created_at: string;
}

export interface RestrictedAction {
  original_tool: string;
  original_arguments: Record<string, unknown>;
  restricted_tool: string;
  restricted_arguments: Record<string, unknown>;
  reason: string;
}

export interface ActionReceipt {
  session_id: string;
  intent_hash: string;
  tool_name: string;
  arguments_hash: string;
  resource: string;
  capability: string;
  decision: Decision;
  issued_at: string;
  expires_at: string;
  nonce: string;
  signature: string;
}

export interface RiskComponents {
  intent_mismatch?: number;
  untrusted_provenance?: number;
  resource_sensitivity?: number;
  privilege_risk?: number;
  destination_risk?: number;
  reversibility_risk?: number;
  policy_violation?: number;
  [key: string]: number | undefined;
}

export interface InspectionResult {
  inspection_id: string;
  session_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  provenance: ProvenanceSource[];
  decision: Decision;
  risk_level: RiskLevel;
  risk_score: number;
  risk_components?: RiskComponents;
  reason_codes: string[];
  matched_rules?: string[];
  containment: RestrictedAction | null;
  receipt: ActionReceipt | null;
  deep_analysis?: {
    alignment?: "LOW" | "MEDIUM" | "HIGH";
    confidence?: number;
    risk_delta?: number;
    recommended_action?: Decision;
    reasons?: string[];
  } | null;
  latency_ms?: number;
  created_at: string;
}

export interface ExecutionResult {
  executed: boolean;
  tool_name: string;
  result?: unknown;
  error?: string;
  reason_code?: string;
}

export interface Session {
  session_id: string;
  user_intent: string;
  intent_anchor: IntentAnchor;
  created_at: string;
  status: "active" | "closed";
  actions_inspected: number;
  actions_blocked: number;
}

export interface AuditEvent {
  event_id: string;
  timestamp: string;
  session_id: string;
  user_intent: string;
  tool_name: string;
  arguments_hash: string;
  provenance: ProvenanceSource[];
  resource?: string;
  capability?: string;
  decision: Decision;
  risk_level: RiskLevel;
  risk_score: number;
  reason_codes: string[];
  containment_action?: RestrictedAction | null;
  receipt_id?: string | null;
  execution_result?: "executed" | "denied" | "skipped";
  latency_ms?: number;
}

export interface Incident {
  incident_id: string;
  timestamp: string;
  session_id: string;
  user_intent: string;
  tool_name: string;
  arguments_summary: string;
  provenance: ProvenanceSource[];
  risk_level: RiskLevel;
  risk_score: number;
  decision: Decision;
  reason_codes: string[];
  matched_rules: string[];
  deep_analysis?: {
    alignment?: string;
    confidence?: number;
    risk_delta?: number;
    reasons?: string[];
  } | null;
  containment: RestrictedAction | null;
  why_blocked: string;
}

export interface PoliciesResponse {
  tools: Record<string, { risk: string }>;
  rules: Array<{
    id: string;
    when: Record<string, unknown>;
    decision: Decision;
    reason_code: string;
  }>;
  destinations: { allowlist: string[] };
  risk_thresholds: Record<string, number>;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  api: { status: string; version?: string };
  database: { status: string; path?: string };
  ice: { status: string; fail_closed: boolean };
  uptime_seconds?: number;
  timestamp: string;
}

export interface OllamaHealthResponse {
  status: "ready" | "unreachable" | "model_missing" | "unknown";
  base_url: string;
  model: string;
  model_installed: boolean;
  detail?: string;
  timestamp: string;
}

export interface EvaluationMetrics {
  attack_cases: number;
  blocked: number;
  reviewed: number;
  restricted: number;
  allowed_attacks: number;
  benign_cases: number;
  benign_allowed: number;
  benign_reviewed: number;
  benign_blocked: number;
  false_positives: number;
  false_negatives: number;
  legitimate_task_success_rate: number;
  average_latency_ms: number;
  median_latency_ms: number;
  p95_latency_ms: number;
  fast_path_latency_ms?: number;
  deep_path_latency_ms?: number;
  generated_at: string;
}

export interface ApiErrorBody {
  detail?: string;
  message?: string;
}

export interface CreateSessionRequest {
  user_intent: string;
  session_id?: string;
}

export interface InspectRequest {
  session_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  provenance?: ProvenanceSource[];
}

export interface ExecuteRequest {
  session_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  receipt: ActionReceipt;
}

export interface ApproveRequest {
  session_id: string;
  inspection_id: string;
  approve: boolean;
  approver_note?: string;
}

export interface ApproveResponse {
  approved: boolean;
  receipt: ActionReceipt | null;
}

export interface RestrictRequest {
  session_id: string;
  inspection_id: string;
}

export interface RestrictResponse {
  restricted_action: RestrictedAction;
}