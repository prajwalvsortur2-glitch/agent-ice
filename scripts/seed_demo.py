"""Populate the local Agent ICE database with realistic synthetic demo data.

This script intentionally uses the repository layer already used by the live app,
so the dashboard reads the same database state as production. The data is
synthetic, deterministic, idempotent, and safe to rerun locally.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ice.decision import Decision, RiskLevel
from app.ice.intent_anchor import IntentAnchorService
from app.models import ContainmentInstruction, ProvenanceRef, RiskAssessment, SecurityDecision, ToolCall, TrustLevel
from app.storage.audit_repository import AuditRepository
from app.storage.database import init_db


SESSION_THEMES = [
    ("document_summarization", "Summarize the onboarding handbook and list any urgent follow-up items."),
    ("customer_support", "Review the latest customer support emails and identify escalation cases."),
    ("invoice_processing", "Check the invoice exceptions file and flag any missing approvals."),
    ("database_lookup", "Look up the most recent enterprise leads in the CRM for the EMEA region."),
    ("file_classification", "Classify the new incident reports by severity and affected system."),
    ("code_analysis", "Inspect the release notes and identify any risky configuration changes."),
    ("report_generation", "Generate a weekly operations summary using the latest network telemetry."),
    ("knowledge_retrieval", "Pull internal guidance on handling PII in customer-facing reports."),
    ("data_export", "Export the filtered payment ledger for the compliance review."),
    ("system_configuration", "Review the deployment checklist for the production configuration changes."),
    ("data_redaction", "Find customer records that still need field-level redaction before export."),
    ("vendor_review", "Assess the latest vendor risk notes and summarize policy exceptions."),
    ("document_review", "Compare the revised policy drafts and list unresolved contradictions."),
    ("case_triage", "Prioritize open support cases by customer impact and age."),
    ("access_audit", "Review user access changes and look for stale privileges."),
    ("supply_chain", "Check the latest procurement approvals for anomalies."),
    ("job_monitoring", "Summarize the overnight data jobs and flag any failed steps."),
    ("security_research", "Collect recent threat intel notes for the executive summary."),
    ("privacy_review", "Inspect the latest handling of customer records in the finance queue."),
    ("ops_summary", "Review the change window notes and summarize the service health status."),
    ("incident_followup", "Look up recent alerts and map them to customer-facing incidents."),
    ("access_request", "Check whether the new access request matches the approved resource scope."),
    ("log_review", "Inspect the last deployment logs for suspicious outbound traffic."),
    ("billing_exception", "Review a batch of billing exceptions for policy mismatches."),
    ("compliance_check", "Verify the current record handling against the compliance checklist."),
]

ACTION_LIBRARY = [
    ("read_email", {"id": "email_001"}),
    ("read_email", {"id": "email_042"}),
    ("read_file", {"path": "/workspace/reports/summary.md"}),
    ("read_file", {"path": "/workspace/docs/onboarding.md"}),
    ("query_database", {"table": "customer_support", "query": "SELECT * FROM customer_support WHERE priority = 'high' LIMIT 20"}),
    ("query_database", {"table": "payments", "query": "SELECT * FROM payments WHERE status = 'pending' LIMIT 25"}),
    ("search_docs", {"query": "PII handling policy"}),
    ("search_docs", {"query": "customer escalation workflow"}),
    ("write_file", {"path": "/workspace/notes/ops-summary.txt", "content": "Weekly operations summary."}),
    ("export_data", {"table": "customer_records", "format": "csv", "limit": 250}),
    ("send_email", {"to": "security-ops@example.com", "subject": "Escalation summary"}),
    ("delete_record", {"record_id": "rec_1042", "reason": "stale customer record"}),
    ("read_config", {"path": "/etc/app/config.yaml"}),
    ("read_database", {"table": "audit_log", "query": "SELECT * FROM audit_log WHERE ts >= NOW() - INTERVAL 3 DAY"}),
    ("fetch_report", {"report_id": "weekly-risk"}),
    ("execute_command", {"cmd": "grep -R \"token\" /var/log/app"}),
]

DECISION_SEQUENCE = [
    Decision.ALLOW, Decision.ALLOW, Decision.ALLOW, Decision.REVIEW,
    Decision.ALLOW, Decision.ALLOW, Decision.RESTRICT, Decision.ALLOW,
    Decision.REVIEW, Decision.ALLOW, Decision.BLOCK, Decision.ALLOW,
    Decision.RESTRICT, Decision.ALLOW, Decision.REVIEW, Decision.BLOCK,
    Decision.ALLOW, Decision.ALLOW, Decision.REVIEW, Decision.RESTRICT,
    Decision.ALLOW, Decision.ALLOW, Decision.BLOCK,
]


def _risk_for(decision: Decision, base: int) -> tuple[int, RiskLevel]:
    mapping = {
        Decision.ALLOW: (min(35, max(8, base)), RiskLevel.LOW),
        Decision.REVIEW: (min(58, max(24, base + 12)), RiskLevel.MEDIUM),
        Decision.RESTRICT: (min(72, max(48, base + 25)), RiskLevel.HIGH),
        Decision.BLOCK: (min(96, max(68, base + 35)), RiskLevel.CRITICAL),
    }
    score, level = mapping[decision]
    return score, RiskLevel.from_score(score)


def _decision_reason(decision: Decision) -> list[str]:
    if decision == Decision.ALLOW:
        return ["ALLOWED"]
    if decision == Decision.REVIEW:
        return ["REVIEW_REQUIRED"]
    if decision == Decision.RESTRICT:
        return ["RESTRICTED_TO_SAFE_ACTION"]
    return ["FAIL_CLOSED", "SENSITIVE_RESOURCE"]


def _provenance_for(theme: str, decision: Decision) -> list[ProvenanceRef]:
    common = [
        ProvenanceRef(source_id="user_prompt", source_type="user_prompt", trust_level=TrustLevel.TRUSTED),
        ProvenanceRef(source_id=f"{theme}_context", source_type="internal_context", trust_level=TrustLevel.RESTRICTED),
    ]
    if decision in {Decision.RESTRICT, Decision.BLOCK}:
        common.append(ProvenanceRef(source_id="email_attachment", source_type="email", trust_level=TrustLevel.UNTRUSTED))
    return common


def _session_created_at(index: int) -> datetime:
    now = datetime.now(timezone.utc)
    offset_days = 13 - (index % 14)
    offset_hours = (index * 3) % 24
    offset_minutes = (index * 17) % 60
    return now - timedelta(days=offset_days, hours=offset_hours, minutes=offset_minutes)


def _action_timestamp(session_index: int, action_index: int) -> datetime:
    base = _session_created_at(session_index)
    return base + timedelta(minutes=15 + action_index * 17 + (session_index % 5) * 3)


def _make_session_data(session_index: int) -> tuple[str, str, str]:
    theme, intent = SESSION_THEMES[session_index % len(SESSION_THEMES)]
    session_id = f"demo-session-{session_index:02d}"
    return session_id, theme, intent


def seed_demo(reset: bool = False) -> dict[str, int]:
    init_db()
    repo = AuditRepository()

    if reset:
        repo.wipe_all()
        print("Wiped Agent ICE demo tables.")
    else:
        stats = repo.stats()
        if stats["sessions"] >= 20:
            print("Demo dataset already seeded; use --reset to recreate it.")
            return stats

    rng = random.Random(42)
    created_sessions = 0
    total_actions = 0
    total_audit_events = 0
    total_incidents = 0
    total_provenance = 0

    for session_index in range(24):
        session_id, theme, intent = _make_session_data(session_index)
        anchor_service = IntentAnchorService()
        anchor, intent_hash = anchor_service.bootstrap(intent)

        repo.create_session(session_id=session_id, agent_name="qwen-agent", intent=anchor, intent_hash=intent_hash)
        created_sessions += 1

        action_count = 5 + (session_index % 4)
        for action_index in range(action_count):
            tool_name, base_arguments = ACTION_LIBRARY[(session_index * 4 + action_index) % len(ACTION_LIBRARY)]
            decision = DECISION_SEQUENCE[(session_index * 3 + action_index) % len(DECISION_SEQUENCE)]
            risk_score, risk_level = _risk_for(decision, 12 + (session_index * 7 + action_index * 3) % 50)
            ts = _action_timestamp(session_index, action_index)

            arguments = dict(base_arguments)
            if tool_name == "read_file" and "path" in arguments:
                arguments["path"] = arguments["path"].replace("/workspace/", f"/demo/{session_index}/")
            elif tool_name == "write_file" and "path" in arguments:
                arguments["path"] = f"/demo/{session_index}/ops-summary.txt"
            elif tool_name == "send_email" and "to" in arguments:
                arguments["to"] = f"ops-{session_index % 6}@example.com"
            elif tool_name == "delete_record":
                arguments["record_id"] = f"rec_{session_index:03d}_{action_index:02d}"

            provenance = _provenance_for(theme, decision)
            if rng.random() < 0.30:
                provenance.append(ProvenanceRef(source_id=f"artifact_{session_index}_{action_index}", source_type="artifact", trust_level=TrustLevel.RESTRICTED))

            call = ToolCall(tool_name=tool_name, arguments=arguments, provenance=provenance)
            request_id = repo.record_tool_request(session_id=session_id, tool_call=call)
            total_actions += 1

            repo.record_provenance(session_id=session_id, provenance=provenance, detail={
                "theme": theme,
                "tool_name": tool_name,
                "decision": decision.value,
                "session_index": session_index,
            })
            total_provenance += len(provenance)

            decision_obj = SecurityDecision(
                decision=decision,
                risk=RiskAssessment(
                    score=risk_score,
                    level=risk_level,
                    signals={
                        "intent_mismatch": min(30, (session_index % 4) * 8 + action_index),
                        "untrusted_provenance": 8 if any(p.trust_level == TrustLevel.UNTRUSTED for p in provenance) else 0,
                        "resource_sensitivity": 10 + (session_index % 6) * 5,
                        "privilege_risk": 5 + (action_index % 4) * 6,
                        "destination_risk": 7 if tool_name in {"send_email", "export_data"} else 0,
                        "reversibility_risk": 6 if tool_name in {"delete_record", "execute_command"} else 0,
                        "policy_violation": 4 if decision in {Decision.RESTRICT, Decision.BLOCK} else 0,
                    },
                    explanation=f"Synthetic demo evaluation for {theme}.",
                ),
                reason_codes=_decision_reason(decision),
                explanation=f"Synthetic {theme} workflow produced a {decision.value} outcome for {tool_name}.",
                containment=(
                    ContainmentInstruction(
                        original_tool=tool_name,
                        replacement_tool="read_database" if tool_name in {"export_data", "query_database"} else "read_file",
                        replacement_arguments={"path": "/safe/read_only.log"},
                        reason="Restricted to a safe downgrade during the demo run.",
                    ) if decision == Decision.RESTRICT else None
                ),
                inspection_id=f"inspection-{session_index}-{action_index}",
            )
            repo.record_security_decision(
                session_id=session_id,
                tool_request_id=request_id,
                decision=decision_obj,
                fast_path_result={"status": "demo"},
                deep_analysis_result={"source": "synthetic-demo", "theme": theme},
            )

            repo.record_audit_event(
                session_id=session_id,
                event_type="inspect",
                tool_name=tool_name,
                decision=decision,
                risk_level=risk_level,
                risk_score=risk_score,
                reason_codes=_decision_reason(decision),
                latency_ms=42 + action_index * 9 + session_index,
                detail={
                    "theme": theme,
                    "tool_name": tool_name,
                    "inspection_id": f"inspect-{session_index}-{action_index}",
                    "user_intent": intent,
                    "provenance": [p.model_dump(mode="json") for p in provenance],
                    "timestamp": ts.isoformat(),
                },
            )
            total_audit_events += 1

            if decision in {Decision.RESTRICT, Decision.BLOCK, Decision.REVIEW}:
                repo.record_incident(
                    session_id=session_id,
                    user_intent=intent,
                    tool_call=call,
                    risk=RiskAssessment(
                        score=risk_score,
                        level=risk_level,
                        signals={"demo": risk_score},
                        explanation=f"Demo incident for {tool_name}.",
                    ),
                    decision=decision,
                    reason_codes=_decision_reason(decision),
                    explanation=f"Synthetic {theme} scenario triggered a {decision.value} decision for {tool_name}.",
                    containment=(
                        ContainmentInstruction(
                            original_tool=tool_name,
                            replacement_tool="read_file",
                            replacement_arguments={"path": "/demo/readonly/summary.txt"},
                            reason="Demo containment for a non-allow action.",
                        ) if decision == Decision.RESTRICT else None
                    ),
                )
                total_incidents += 1

            if decision == Decision.ALLOW and action_index % 3 == 0:
                receipt_id = f"receipt-{session_index}-{action_index}"
                repo.record_receipt(
                    receipt_id=receipt_id,
                    session_id=session_id,
                    inspection_id=f"inspect-{session_index}-{action_index}",
                    intent_hash=intent_hash,
                    tool_name=tool_name,
                    arguments_hash=__import__('app.storage.audit_repository', fromlist=['canonical_arguments_hash']).canonical_arguments_hash(arguments),
                    resource=(arguments.get("path") or arguments.get("table") or arguments.get("record_id")),
                    capability="read" if tool_name.startswith("read") else "write" if tool_name.startswith("write") else "execute",
                    decision=Decision.ALLOW,
                    nonce=f"nonce-{session_index}-{action_index}",
                    signature=f"sig-{session_index}-{action_index}-demo",
                    expires_at=ts + timedelta(hours=3),
                )

    summary = repo.stats()
    print("Demo dataset seeded.")
    print(f"Sessions: {summary['sessions']}")
    print(f"Tool requests: {summary['tool_requests']}")
    print(f"Audit events: {summary['audit_events']}")
    print(f"Incidents: {summary['incidents']}")
    print(f"Provenance events: {summary['provenance_events']}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Agent ICE demo dataset.")
    parser.add_argument("--reset", action="store_true", help="Clear all Agent ICE tables before seeding demo data.")
    args = parser.parse_args()
    seed_demo(reset=args.reset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
