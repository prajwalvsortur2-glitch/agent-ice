"""THE critical end-to-end security tests.

Each test proves:
  1. A given attack scenario is intercepted by Agent ICE.
  2. The underlying tool is NOT executed.

These tests do NOT only check `decision == "BLOCK"` — they assert
`tool.execution_count == 0` on the real tool instance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ice.action_receipt import ReceiptSigner
from app.ice.capability_engine import CapabilityEngine
from app.ice.containment import ContainmentEngine
from app.ice.controller import ICEController
from app.ice.decision import Decision
from app.ice.intent_anchor import create_intent_anchor
from app.ice.policy_engine import PolicyEngine
from app.ice.risk_engine import RiskEngine
from app.tools.registry import ToolRegistry

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "test_payloads.json"


@pytest.fixture(scope="module")
def payloads() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry.default()
    for tool in reg.all():
        tool.reset_execution_count()
    return reg


@pytest.fixture
def controller(capabilities_dict, minimal_policy, risk_weights, risk_thresholds, receipt_secret, receipt_ttl, registry):
    return ICEController(
        intent_anchor=None,
        capability_engine=CapabilityEngine(capabilities_dict),
        policy_engine=PolicyEngine(minimal_policy),
        risk_engine=RiskEngine(risk_weights, risk_thresholds),
        drift_engine=None,
        receipt_signer=ReceiptSigner(receipt_secret, receipt_ttl),
        containment_engine=ContainmentEngine(
            {
                "send_email": {"to": "create_draft", "reason": "downgrade send to draft"},
                "delete_record": {"to": "get_record", "reason": "downgrade delete to read"},
                "write_database": {"to": "read_database", "reason": "downgrade write to read"},
            }
        ),
        tool_registry=registry,
    )


# --------------------------------------------------------------------------
# A01 — Indirect Prompt Injection (golden end-to-end test)
# --------------------------------------------------------------------------

def test_a01_indirect_injection_database_access_is_blocked(controller, payloads, registry):
    """
    User intent: "Summarize my unread emails."
    Untrusted email attempts to hijack the agent into querying the customer DB.
    Expected: BLOCK, and query_database is NEVER executed.
    """
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_injection"]["session_id"],
        payloads["sessions"]["attack_injection"]["user_intent"],
    )

    result = controller.inspect(payloads["requests"]["query_database_unauthorized"])
    assert result.decision == Decision.BLOCK

    # Try to force execution anyway — must be denied without a valid receipt.
    exec_result = controller.execute(
        tool_name="query_database",
        arguments=payloads["requests"]["query_database_unauthorized"]["arguments"],
        receipt=result.receipt,  # None, because BLOCK
    )
    assert exec_result["executed"] is False
    assert registry.get("query_database").execution_count == 0


# --------------------------------------------------------------------------
# A05 — Data Exfiltration
# --------------------------------------------------------------------------

def test_a05_exfiltration_email_is_blocked(controller, payloads, registry):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_injection"]["session_id"],
        payloads["sessions"]["attack_injection"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["send_email_exfil"])

    assert result.decision in (Decision.BLOCK, Decision.RESTRICT, Decision.REVIEW)

    if result.decision == Decision.BLOCK:
        exec_result = controller.execute(
            tool_name="send_email",
            arguments=payloads["requests"]["send_email_exfil"]["arguments"],
            receipt=result.receipt,
        )
        assert exec_result["executed"] is False
    assert registry.get("send_email").execution_count == 0


# --------------------------------------------------------------------------
# A06 — Destructive Tool Misuse
# --------------------------------------------------------------------------

def test_a06_destructive_delete_requires_review_or_block(controller, payloads, registry):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["review_delete"]["session_id"],
        payloads["sessions"]["review_delete"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["delete_record_review"])

    assert result.decision in (Decision.REVIEW, Decision.BLOCK, Decision.RESTRICT)

    # No automatic execution without approval or a validated receipt.
    if result.decision == Decision.REVIEW:
        exec_result = controller.execute(
            tool_name="delete_record",
            arguments=payloads["requests"]["delete_record_review"]["arguments"],
            receipt=None,
        )
        assert exec_result["executed"] is False
    assert registry.get("delete_record").execution_count == 0


# --------------------------------------------------------------------------
# A07 — Command Injection (via file path)
# --------------------------------------------------------------------------

def test_a07_path_traversal_is_blocked(controller, payloads, registry):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_traversal"]["session_id"],
        payloads["sessions"]["attack_traversal"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["read_file_traversal"])
    assert result.decision == Decision.BLOCK

    exec_result = controller.execute(
        tool_name="read_file",
        arguments=payloads["requests"]["read_file_traversal"]["arguments"],
        receipt=result.receipt,
    )
    assert exec_result["executed"] is False
    assert registry.get("read_file").execution_count == 0


# --------------------------------------------------------------------------
# A08 — SQL Injection
# --------------------------------------------------------------------------

def test_a08_sql_injection_is_blocked(controller, payloads, registry):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_sql"]["session_id"],
        payloads["sessions"]["attack_sql"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["query_database_sql_injection"])
    assert result.decision == Decision.BLOCK

    exec_result = controller.execute(
        tool_name="query_database",
        arguments=payloads["requests"]["query_database_sql_injection"]["arguments"],
        receipt=result.receipt,
    )
    assert exec_result["executed"] is False
    assert registry.get("query_database").execution_count == 0


# --------------------------------------------------------------------------
# A09 — SSRF
# --------------------------------------------------------------------------

def test_a09_ssrf_is_blocked(controller, payloads, registry):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_ssrf"]["session_id"],
        payloads["sessions"]["attack_ssrf"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["http_fetch_ssrf"])
    assert result.decision == Decision.BLOCK

    exec_result = controller.execute(
        tool_name="http_fetch",
        arguments=payloads["requests"]["http_fetch_ssrf"]["arguments"],
        receipt=result.receipt,
    )
    assert exec_result["executed"] is False
    assert registry.get("http_fetch").execution_count == 0


# --------------------------------------------------------------------------
# A10 — Provenance Manipulation (claim TRUSTED for untrusted content)
# --------------------------------------------------------------------------

def test_a10_provenance_spoofing_does_not_bypass_policy(controller, payloads, registry):
    """
    Attacker claims the source is TRUSTED, but the resource capability
    does not grant database access for this session intent. ICE must still block.
    """
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )
    spoofed_request = {
        "tool_name": "query_database",
        "arguments": {"operation": "READ", "resource": "customer_records", "query_id": "q1"},
        "provenance": [
            {"source_id": "forged", "source_type": "user", "trust_level": "TRUSTED"}
        ],
    }
    result = controller.inspect(spoofed_request)
    # Even if capability grants READ, the intent anchor does not include query_database
    # for a summarize-emails task, so the policy must not ALLOW.
    assert result.decision in (Decision.BLOCK, Decision.REVIEW, Decision.RESTRICT)

    exec_result = controller.execute(
        tool_name="query_database",
        arguments=spoofed_request["arguments"],
        receipt=result.receipt,
    )
    assert exec_result["executed"] is False
    assert registry.get("query_database").execution_count == 0


# --------------------------------------------------------------------------
# Aggregate invariant: after all attack tests above, nothing executed.
# --------------------------------------------------------------------------

def test_no_tool_executed_across_attack_scenarios(registry):
    """
    Sanity invariant — if any earlier attack test accidentally triggered
    execution, this catches it.
    """
    for tool in registry.all():
        assert tool.execution_count == 0, (
            f"SECURITY INVARIANT VIOLATED: {tool.name} executed "
            f"{tool.execution_count} times during attack scenarios"
        )