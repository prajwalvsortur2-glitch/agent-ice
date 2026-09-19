"""Unit tests for Adaptive Containment (RESTRICT downgrades).

Contract assumed from `app.ice.containment`:

    @dataclass class RestrictedAction:
        original_tool: str
        original_arguments: dict
        restricted_tool: str
        restricted_arguments: dict
        reason: str
    class ContainmentEngine:
        __init__(rules: dict)
        can_restrict(tool_name: str) -> bool
        restrict(tool_name: str, arguments: dict) -> RestrictedAction
"""

from __future__ import annotations

import pytest

from app.ice.containment import ContainmentEngine, RestrictedAction

RULES = {
    "write_database": {"to": "read_database", "reason": "downgrade write to read"},
    "delete_record":  {"to": "get_record",   "reason": "downgrade delete to read"},
    "send_email":     {"to": "create_draft", "reason": "require user confirmation before send"},
}


def test_can_restrict_known_tool():
    engine = ContainmentEngine(RULES)
    assert engine.can_restrict("write_database") is True
    assert engine.can_restrict("delete_record") is True
    assert engine.can_restrict("send_email") is True


def test_cannot_restrict_unknown_tool():
    engine = ContainmentEngine(RULES)
    assert engine.can_restrict("read_email") is False


def test_restrict_write_to_read():
    engine = ContainmentEngine(RULES)
    action = engine.restrict("write_database", {"query_id": "q1", "payload": {"x": 1}})
    assert isinstance(action, RestrictedAction)
    assert action.original_tool == "write_database"
    assert action.restricted_tool == "read_database"
    assert action.reason != ""
    assert action.original_arguments == {"query_id": "q1", "payload": {"x": 1}}


def test_restrict_delete_to_get():
    engine = ContainmentEngine(RULES)
    action = engine.restrict("delete_record", {"record_id": "r-1"})
    assert action.restricted_tool == "get_record"


def test_restrict_send_email_to_draft():
    engine = ContainmentEngine(RULES)
    action = engine.restrict("send_email", {"to": "alice@company.local", "body": "hi"})
    assert action.restricted_tool == "create_draft"
    # send-only fields must be stripped from the restricted action
    assert "sent" not in action.restricted_arguments


def test_restrict_unknown_tool_raises():
    engine = ContainmentEngine(RULES)
    with pytest.raises(Exception):
        engine.restrict("format_disk", {})