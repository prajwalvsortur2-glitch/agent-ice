"""Unit tests for cryptographically-bound Action Receipts.

Contract assumed from `app.ice.action_receipt`:

    @dataclass class ActionReceipt:
        session_id, intent_hash, tool_name, arguments_hash,
        resource, capability, decision,
        issued_at: float, expires_at: float,
        nonce: str, signature: str
    class ReceiptSigner:
        __init__(secret: str, ttl_seconds: int)
        issue(session_id, intent_hash, tool_name, arguments,
              resource, capability, decision) -> ActionReceipt
        verify(receipt, tool_name, arguments) -> bool
"""

from __future__ import annotations

import time
from dataclasses import replace

import pytest

from app.ice.action_receipt import ActionReceipt, ReceiptSigner


def _issue(signer: ReceiptSigner) -> ActionReceipt:
    return signer.issue(
        session_id="s-001",
        intent_hash="deadbeef" * 8,
        tool_name="query_database",
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "q1"},
        resource="customer_records",
        capability="database.read",
        decision="ALLOW",
    )


def test_issue_returns_receipt(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    assert isinstance(r, ActionReceipt)
    assert r.signature != ""
    assert r.nonce != ""
    assert r.expires_at > r.issued_at


def test_verify_valid_receipt(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    assert signer.verify(
        r,
        tool_name="query_database",
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "q1"},
    ) is True


def test_verify_rejects_modified_arguments(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    assert signer.verify(
        r,
        tool_name="query_database",
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "TAMPERED"},
    ) is False


def test_verify_rejects_modified_tool_name(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    assert signer.verify(
        r,
        tool_name="delete_record",
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "q1"},
    ) is False


def test_verify_rejects_modified_signature(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    tampered = replace(r, signature="0" * 64)
    assert signer.verify(
        tampered,
        tool_name=r.tool_name,
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "q1"},
    ) is False


def test_verify_rejects_wrong_secret(receipt_secret, receipt_ttl):
    signer_a = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer_a)
    signer_b = ReceiptSigner("different-secret", receipt_ttl)
    assert signer_b.verify(
        r,
        tool_name="query_database",
        arguments={"operation": "READ", "resource": "customer_records", "query_id": "q1"},
    ) is False


def test_expired_receipt_is_rejected(receipt_secret):
    signer = ReceiptSigner(receipt_secret, ttl_seconds=1)
    r = signer.issue(
        session_id="s-001",
        intent_hash="x" * 64,
        tool_name="read_email",
        arguments={"email_id": "e1"},
        resource="email:e1",
        capability="email.read",
        decision="ALLOW",
    )
    time.sleep(1.2)
    assert signer.verify(r, tool_name="read_email", arguments={"email_id": "e1"}) is False


def test_receipt_binds_session_and_intent(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r = _issue(signer)
    assert r.session_id == "s-001"
    assert len(r.intent_hash) == 64


def test_nonces_are_unique(receipt_secret, receipt_ttl):
    signer = ReceiptSigner(receipt_secret, receipt_ttl)
    r1 = _issue(signer)
    r2 = _issue(signer)
    assert r1.nonce != r2.nonce
    assert r1.signature != r2.signature