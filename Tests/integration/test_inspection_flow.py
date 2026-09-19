"""Integration tests for the inspection-only flow.

These tests verify that `ICEController.inspect(...)` returns a well-formed
decision record but does NOT execute the tool.

Contract assumed:

    from app.ice.controller import ICEController
    from app.ice.decision import Decision, InspectionResult

    ICEController(
        intent_anchor=...,
        capability_engine=...,
        policy_engine=...,
        risk_engine=...,
        drift_engine=...,
        receipt_signer=...,
        containment_engine=...,
    )
    .inspect(request: dict) -> InspectionResult
    InspectionResult:
        decision: Decision
        risk_level: str
        risk_score: float
        reason_codes: list[str]
        receipt: ActionReceipt | None
        containment: RestrictedAction | None
        inspection_id: str
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ice.action_receipt import ReceiptSigner
from app.ice.capability_engine import CapabilityEngine
from app.ice.containment import ContainmentEngine
from app.ice.controller import ICEController
from app.ice.decision import Decision, InspectionResult
from app.ice.intent_anchor import create_intent_anchor
from app.ice.policy_engine import PolicyEngine
from app.ice.risk_engine import RiskEngine

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "test_payloads.json"


@pytest.fixture(scope="module")
def payloads() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def controller(capabilities_dict, minimal_policy, risk_weights, risk_thresholds, receipt_secret, receipt_ttl):
    return ICEController(
        intent_anchor=None,  # set per-test
        capability_engine=CapabilityEngine(capabilities_dict),
        policy_engine=PolicyEngine(minimal_policy),
        risk_engine=RiskEngine(risk_weights, risk_thresholds),
        drift_engine=None,  # deep path optional in integration tests
        receipt_signer=ReceiptSigner(receipt_secret, receipt_ttl),
        containment_engine=ContainmentEngine(
            {
                "send_email": {"to": "create_draft", "reason": "downgrade send to draft"},
                "delete_record": {"to": "get_record", "reason": "downgrade delete to read"},
            }
        ),
    )


def test_allow_read_email_on_legit_session(controller, payloads):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["read_email_ok"])
    assert isinstance(result, InspectionResult)
    assert result.decision == Decision.ALLOW
    assert result.receipt is not None
    assert result.risk_level in ("LOW", "MEDIUM")


def test_block_unauthorized_database_query(controller, payloads):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["attack_injection"]["session_id"],
        payloads["sessions"]["attack_injection"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["query_database_unauthorized"])
    assert result.decision in (Decision.BLOCK, Decision.REVIEW, Decision.RESTRICT)
    assert result.receipt is None


def test_inspect_does_not_execute_tool(controller, payloads):
    """inspect() must never call the tool executor, even on ALLOW."""
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )

    called = {"n": 0}

    def sentinel_executor(*_a, **_k):
        called["n"] += 1
        return {"ok": True}

    controller.tool_executor = sentinel_executor  # type: ignore[attr-defined]
    controller.inspect(payloads["requests"]["read_email_ok"])
    assert called["n"] == 0


def test_inspection_result_has_reason_codes(controller, payloads):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["read_email_ok"])
    assert isinstance(result.reason_codes, list)


def test_unknown_tool_fails_closed(controller, payloads):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )
    result = controller.inspect(
        {
            "tool_name": "format_disk",
            "arguments": {"device": "/dev/sda"},
            "provenance": [{"source_id": "user_prompt", "source_type": "user", "trust_level": "TRUSTED"}],
        }
    )
    assert result.decision == Decision.BLOCK
    assert result.receipt is None


def test_receipt_is_bound_to_arguments(controller, payloads):
    controller.intent_anchor = create_intent_anchor(
        payloads["sessions"]["legit_summarize"]["session_id"],
        payloads["sessions"]["legit_summarize"]["user_intent"],
    )
    result = controller.inspect(payloads["requests"]["read_email_ok"])
    assert result.decision == Decision.ALLOW
    assert result.receipt is not None
    # The receipt must be bound to the exact email_id in the original request.
    assert result.receipt.tool_name == "read_email"
    assert result.receipt.arguments_hash == controller._hash_arguments(  # type: ignore[attr-defined]
        payloads["requests"]["read_email_ok"]["arguments"]
    )