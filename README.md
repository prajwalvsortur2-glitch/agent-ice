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
