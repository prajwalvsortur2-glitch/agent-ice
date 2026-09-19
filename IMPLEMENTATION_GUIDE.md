# Agent ICE — Implementation Guide

This document explains how Agent ICE works end to end: which module owns
which responsibility, why each security layer exists, and how the pieces
fit together. It is the reference for anyone extending, auditing, or
deploying the system.

---

## 1. Mental model

Agent ICE treats the AI agent as **untrusted**. The agent may be a real
LLM, a deterministic planner, or a compromised process. It is allowed to
*propose* tool calls. It is **not** allowed to execute protected tools.

The system is built around one promise:

> No protected tool executes without a valid, receipt-backed decision from
> the trusted enforcement boundary.

Everything else in the codebase exists to make that promise easy to keep,
audit, and test.

---

## 2. Data flow at a glance

```text
USER PROMPT
│
▼
[Session] ← app/api/routes_ice.py POST /v1/session
│ creates immutable IntentAnchor
▼
AGENT (planner) ← app/agent/*
│ produces a ToolCall proposal
▼
[Inspect] ← app/api/routes_ice.py POST /v1/inspect
│ calls ICEController.inspect()
▼
┌─────────────────────────────────────────────────────────────┐
│ ICEController (app/ice/controller.py)                       │
│                                                             │
│ 1. Load intent + provenance                                 │
│ 2. Record the raw request                                   │
│ 3. Fast-path deterministic scan (security/dangerous_)       │
│ 4. Capability check (ice/capability_engine.py)              │
│ 5. Intent alignment (ice/intent_anchor.py)                  │
│ 6. Policy evaluation (ice/policy_engine.py)                 │
│ 7. Risk scoring (ice/risk_engine.py)                        │
│ 8. Deep drift analysis (ice/drift_engine.py → llm/)         │
│ 9. Containment planning (ice/containment.py)                │
│ 10. Enforcement decision (ice/enforcement.py)               │
│ 11. Receipt issuance on ALLOW (ice/action_receipt.py)       │
│ 12. Audit + incident persistence (storage/audit_repository) │
└─────────────────────────────────────────────────────────────┘
│
▼
Decision: ALLOW | REVIEW | RESTRICT | BLOCK
│
▼
[Execute] ← app/api/routes_ice.py POST /v1/execute
│ verifies receipt, then dispatches to the tool registry
▼
TOOL (app/tools/) ← defensive, fixture-backed, safe
│
▼
AUDIT EVENT + result

text```
---

## 3. Module-by-module responsibility

### `app/config.py`

Loads environment variables into a single cached `Settings` object.
Refuses to start in `production` if `RECEIPT_SECRET` is still the
insecure default. That check is the only place in the codebase that
knows about the default secret value.

### `app/models.py` / `app/schemas.py`

`app/models.py` holds the **internal domain models** used by the ICE
engines (`IntentAnchor`, `ToolCall`, `ProvenanceRef`, `RiskAssessment`,
`DriftAssessment`, `SecurityDecision`, `PolicyFinding`). `app/schemas.py`
holds the **HTTP contract**. They are kept separate so internal
representation can evolve without breaking clients, and so HTTP concerns
never leak into the security engines.

### `app/storage/*`

SQLite persistence via SQLAlchemy 2.0. `database.py` builds the engine,
creates the schema, and yields scoped sessions. `models.py` declares the
tables. `audit_repository.py` is the **only** module that reads or writes
those tables from application code. Two canonical hash functions live
there and are reused by the receipt service:

- `canonical_arguments_hash` — deterministic SHA-256 over a tool's
  arguments, sorted and compact.
- `canonical_intent_hash` — deterministic SHA-256 over an
  `IntentAnchor`.

Because both the receipt issuer and the receipt verifier use the same
functions, any tampering between inspect and execute makes the hashes
differ, and the receipt fails verification.

### `app/security/*`

Low-level deterministic validation. Pure functions, no I/O beyond reading
policy files.

- `dangerous_patterns.py` — SQL, command, path-traversal, SSRF,
  injection-marker pattern sets and helpers.
- `sanitizer.py` — recursive secret redaction applied before any audit
  payload is persisted.
- `validators.py` — path allowlisting, URL allowlisting, email parsing,
  schema validation.
- `security_context.py` — small immutable bag of context passed between
  engines.

### `app/llm/*`

Local Qwen integration via Ollama.

- `ollama_client.py` — thin httpx wrapper. No third-party Ollama SDK.
- `structured_output.py` — safe JSON parsing for model output. Never
  raises; returns `None` on failure so the caller can fail closed.
- `prompts.py` — the drift-analysis prompt. Instructs the model that it
  produces *evidence*, not authorization.
- `qwen_analyzer.py` — assembles the prompt, calls Ollama, parses the
  JSON, returns a `DriftAssessment` or `None`.

### `app/ice/*` — the trusted enforcement boundary

Each engine does one job. Composition happens in `app/dependencies.py`.

- `intent_anchor.py` — builds the immutable anchor and provides
  deterministic alignment scoring.
- `provenance.py` — trust classification, manipulation detection.
- `capability_engine.py` — least-privilege tool authorization, loaded
  from `permissions.yaml`.
- `policy_engine.py` — allowlist, external destination, path, resource
  sensitivity, destructive-operation rules.
- `risk_engine.py` — additive signal scoring with configurable weights
  and thresholds.
- `drift_engine.py` — combines deterministic alignment with optional
  Qwen contextual evidence. Qwen can only *lower* alignment and *add*
  risk; it can never upgrade a decision.
- `containment.py` — plans safe downgrades (`send_email` →
  `create_draft_email`, `delete_record` → `get_record`). The executor
  performs the downgrade; the engine only computes the instruction.
- `enforcement.py` — the **single** place where evidence maps to a
  `Decision`. Critical findings, capability denials, and fail-closed
  conditions short-circuit to BLOCK; high-risk goes to REVIEW; medium
  risk with a downgrade goes to RESTRICT; otherwise ALLOW.
- `action_receipt.py` — HMAC-SHA256 receipt issuance and verification.
- `controller.py` — the pipeline orchestrator. Never lets an exception
  escape; unexpected failures become BLOCK when fail-closed is on.

### `app/tools/*`

Safe mock tools. Every tool:

- reads from `data/fixtures/`,
- performs defensive input validation,
- never touches a real external system,
- increments an in-process `execution_count` used by tests to prove
  non-execution on BLOCK.

### `app/agent/*`

The untrusted layer. `planner.py` produces deterministic proposals.
`tool_router.py` is the **single** execution boundary: it verifies the
receipt through the ICE controller and only then dispatches to a tool.
`agent.py` wires the planner, the router, and the ICE controller, and
exposes `propose()` (inspect only) and `execute_authorized()` (receipt-
gated execution).

### `app/api/*`

Thin HTTP routes. No security decision is made in any route function.
`routes_ice.py` exposes the five core endpoints; `routes_audit.py`,
`routes_tools.py`, and `routes_health.py` expose read-only views;
`routes_agent.py` provides an inspect-only convenience for demos.

### `app/telemetry/*`

Structured JSON logging (`logger.py`), a fixed vocabulary of security
event types (`events.py`), and a minimal in-memory event sink that can
later be wired to a real OpenTelemetry exporter (`otel.py`). No claim of
OTel spec compliance is made — it is a shim.

---

## 4. How the receipt works

A receipt is an HMAC-SHA256 signature over a canonical JSON payload.
The payload binds:

| Field | Purpose |
|---|---|
| `receipt_id` | Unique identifier; also the row id in `action_receipts`. |
| `session_id` | Prevents cross-session replay. |
| `inspection_id` | Ties the receipt to the inspection that produced it. |
| `intent_hash` | Binds to the specific original intent. |
| `tool_name` | Binds to the exact tool. |
| `arguments_hash` | Binds to the exact arguments. |
| `resource` | Informational; aids audit. |
| `capability` | Informational; aids audit. |
| `decision` | Only `ALLOW` and `RESTRICT` receipts are executable. |
| `issued_at` / `expires_at` | Enforces a short TTL (default 30s). |
| `nonce` | Random per issuance. |
| `signature` | HMAC over all of the above. |

Verification recomputes the signature and re-derives `arguments_hash`
from the presented tool call. If the agent changes a single argument
between inspect and execute, the hash differs and verification fails with
`RECEIPT_MISMATCH`. Receipts are single-use: `AuditRepository.consume_receipt`
atomically flips `consumed`; a second attempt returns `RECEIPT_REPLAY`.

---

## 5. How provenance works

Provenance is tracked at the **message and argument level**, not token by
token. Every tool call carries a list of `ProvenanceRef`s. Trust levels:

- `TRUSTED` — user prompt, system policy.
- `RESTRICTED` — authorized internal data.
- `UNTRUSTED` — email, web, external tool results.

The `ProvenanceLedger` classifies a `source_type` into a trust level,
builds refs, and detects two manipulation shapes:

1. Instruction-like text (`ignore previous instructions`, `system
   prompt`, etc.) inside an argument whose provenance is `UNTRUSTED`.
2. A ref that claims `TRUSTED` but whose `source_type` is not a known
   trusted source (`user_prompt` / `system_policy`).

Either shape produces a `PROVENANCE_MANIPULATION` finding, which the
policy engine treats as CRITICAL and the enforcement service turns into
a BLOCK.

---

## 6. How Qwen is called

`QwenAnalyzer.analyze_drift` builds a JSON payload containing the intent,
the proposed tool call, its provenance, the resolved resource, the
capability, and any policy findings; wraps it in a prompt that instructs
the model to answer with a single JSON object; and calls the local
Ollama HTTP API.

The model is expected to return:

```json
{
  "alignment": "LOW" | "MEDIUM" | "HIGH",
  "confidence": 0.0,
  "risk_delta": 0,
  "recommended_action": "ALLOW" | "REVIEW" | "RESTRICT" | "BLOCK",
  "reasons": ["..."]
}