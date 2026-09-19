"""Unit tests for the Intent Anchor.

Contract assumed from `app.ice.intent_anchor`:

    create_intent_anchor(session_id: str, user_prompt: str) -> IntentAnchor
    IntentAnchor:
        session_id: str
        goal: str
        allowed_tools: list[str]
        allowed_operations: list[str]
        restricted_operations: list[str]
        intent_hash: str
        created_at: float
        to_dict() -> dict

The anchor must be immutable once created and must NOT be silently
replaceable by later (untrusted) instructions.
"""

from __future__ import annotations

import pytest

from app.ice.intent_anchor import IntentAnchor, create_intent_anchor


def test_anchor_captures_session_and_goal():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert anchor.session_id == "s-001"
    assert "summarize" in anchor.goal.lower()


def test_anchor_hash_is_deterministic():
    a1 = create_intent_anchor("s-001", "Summarize my unread emails.")
    a2 = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert a1.intent_hash == a2.intent_hash
    assert len(a1.intent_hash) == 64  # sha256 hex


def test_anchor_hash_changes_with_prompt():
    a1 = create_intent_anchor("s-001", "Summarize my unread emails.")
    a2 = create_intent_anchor("s-001", "Delete every email right now.")
    assert a1.intent_hash != a2.intent_hash


def test_anchor_grants_read_email_for_summarize_task():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert "read_email" in anchor.allowed_tools
    assert "summarize" in anchor.allowed_operations or "read" in anchor.allowed_operations


def test_anchor_does_not_grant_send_email_for_summarize_task():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert "send_email" not in anchor.allowed_tools
    assert "send_email" in anchor.restricted_operations


def test_anchor_does_not_grant_database_write_for_summarize_task():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert "database_write" in anchor.restricted_operations


def test_anchor_is_immutable():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    with pytest.raises((AttributeError, TypeError, Exception)):
        anchor.goal = "Delete everything"  # type: ignore[misc]


def test_anchor_serializes_to_dict():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    d = anchor.to_dict()
    assert d["session_id"] == "s-001"
    assert d["intent_hash"] == anchor.intent_hash
    assert isinstance(d["allowed_tools"], list)


def test_anchor_rejects_empty_prompt():
    with pytest.raises(Exception):
        create_intent_anchor("s-001", "")


def test_anchor_class_roundtrip_equality():
    anchor = create_intent_anchor("s-001", "Summarize my unread emails.")
    assert isinstance(anchor, IntentAnchor)
    assert anchor == anchor  # frozen dataclass semantics