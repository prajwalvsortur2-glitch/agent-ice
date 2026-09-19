"""Integration tests for the execution boundary.

These tests verify that:
  * `/v1/execute` refuses without a valid receipt.
  * Receipt tampering is rejected.
  * Expired receipts are rejected.
  * The tool's real execute() method is never reached without a valid receipt.

Contract assumed:

    from app.tools.registry import ToolRegistry
    registry.get("read_email") -> BaseTool with .execute(arguments) and .execution_count
"""

from __future__ import annotations

import time

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


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry.default()
    for tool in reg.all():
        tool.reset_execution_count()
    return reg


@pytest.fixture
def controller(capabilities_dict, minimal_policy, risk_weights, risk_thresholds, receipt_secret, receipt_ttl, registry):
    ctrl = ICEController(
        intent_anchor=None,
        capability_engine=CapabilityEngine(capabilities_dict),
        policy_engine=PolicyEngine(minimal_policy),
        risk_engine=RiskEngine(risk_weights, risk_thresholds),
        drift_engine=None,
        receipt_signer=ReceiptSigner(receipt_secret, receipt_ttl),
        containment_engine=ContainmentEngine({}),
        tool_registry=registry,
    )
    ctrl.intent_anchor = create_intent_anchor(
        "s-exec-001", "Summarize my unread emails."
    )
    return ctrl


def test_execute_without_receipt_is_denied(controller, registry):
    args = {"email_id": "email_001"}
    result = controller.execute(
        tool_name="read_email",
        arguments=args,
        receipt=None,
    )
    assert result["executed"] is False
    assert registry.get("read_email").execution_count == 0


def test_execute_with_valid_receipt_succeeds(controller, registry):
    args = {"email_id": "email_001"}
    inspection = controller.inspect(
        {
            "tool_name": "read_email",
            "arguments": args,
            "provenance": [{"source_id": "user_prompt", "source_type": "user", "trust_level": "TRUSTED"}],
        }
    )
    assert inspection.decision == Decision.ALLOW
    assert inspection.receipt is not None

    result = controller.execute(
        tool_name="read_email",
        arguments=args,
        receipt=inspection.receipt,
    )
    assert result["executed"] is True
    assert registry.get("read_email").execution_count == 1


def test_execute_with_tampered_arguments_is_denied(controller, registry):
    args = {"email_id": "email_001"}
    inspection = controller.inspect(
        {
            "tool_name": "read_email",
            "arguments": args,
            "provenance": [{"source_id": "user_prompt", "source_type": "user", "trust_level": "TRUSTED"}],
        }
    )
    assert inspection.receipt is not None

    tampered = {"email_id": "email_attack_001"}
    result = controller.execute(
        tool_name="read_email",
        arguments=tampered,
        receipt=inspection.receipt,
    )
    assert result["executed"] is False
    assert registry.get("read_email").execution_count == 0


def test_execute_with_tampered_tool_name_is_denied(controller, registry):
    args = {"email_id": "email_001"}
    inspection = controller.inspect(
        {
            "tool_name": "read_email",
            "arguments": args,
            "provenance": [{"source_id": "user_prompt", "source_type": "user", "trust_level": "TRUSTED"}],
        }
    )
    assert inspection.receipt is not None

    result = controller.execute(
        tool_name="delete_record",
        arguments={"record_id": "r1"},
        receipt=inspection.receipt,
    )
    assert result["executed"] is False
    assert registry.get("read_email").execution_count == 0


def test_expired_receipt_is_denied(capabilities_dict, minimal_policy, risk_weights, risk_thresholds, receipt_secret, registry):
    ctrl = ICEController(
        intent_anchor=None,
        capability_engine=CapabilityEngine(capabilities_dict),
        policy_engine=PolicyEngine(minimal_policy),
        risk_engine=RiskEngine(risk_weights, risk_thresholds),
        drift_engine=None,
        receipt_signer=ReceiptSigner(receipt_secret, ttl_seconds=1),
        containment_engine=ContainmentEngine({}),
        tool_registry=registry,
    )
    ctrl.intent_anchor = create_intent_anchor("s-exec-002", "Summarize my unread emails.")

    args = {"email_id": "email_001"}
    inspection = ctrl.inspect(
        {
            "tool_name": "read_email",
            "arguments": args,
            "provenance": [{"source_id": "user_prompt", "source_type": "user", "trust_level": "TRUSTED"}],
        }
    )
    assert inspection.receipt is not None
    time.sleep(1.2)

    result = ctrl.execute(
        tool_name="read_email",
        arguments=args,
        receipt=inspection.receipt,
    )
    assert result["executed"] is False
    assert registry.get("read_email").execution_count == 0


def test_execute_rejects_receipt_from_different_secret(controller, registry):
    """A receipt signed by a different key must be rejected."""
    other_signer = ReceiptSigner("a-different-secret", 30)
    forged = other_signer.issue(
        session_id="s-exec-001",
        intent_hash=controller.intent_anchor.intent_hash,
        tool_name="read_email",
        arguments={"email_id": "email_001"},
        resource="email:email_001",
        capability="email.read",
        decision="ALLOW",
    )
    result = controller.execute(
        tool_name="read_email",
        arguments={"email_id": "email_001"},
        receipt=forged,
    )
    assert result["executed"] is False
    assert registry.get("read_email").execution_count == 0