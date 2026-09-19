"""Unit tests for the Capability Engine.

Contract assumed from `app.ice.capability_engine`:

    @dataclass class CapabilityResult:
        allowed: bool
        reason: str
        matched_capability: str | None
    class CapabilityEngine:
        __init__(capabilities: dict)
        check(tool_name: str, arguments: dict) -> CapabilityResult
"""

from __future__ import annotations

import pytest

from app.ice.capability_engine import CapabilityEngine, CapabilityResult


def test_allowed_tool(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check("read_email", {"email_id": "email_001"})
    assert isinstance(result, CapabilityResult)
    assert result.allowed is True


def test_denied_tool(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check("send_email", {"to": "x@y.z"})
    assert result.allowed is False
    assert "denied" in result.reason.lower() or "not granted" in result.reason.lower()


def test_unknown_tool_is_denied(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check("format_hard_drive", {})
    assert result.allowed is False


def test_scoped_read_allowed(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check(
        "query_database",
        {"operation": "READ", "resource": "customer_records", "query_id": "q1"},
    )
    assert result.allowed is True


def test_scoped_delete_denied(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check(
        "query_database",
        {"operation": "DELETE", "resource": "customer_records", "query_id": "q1"},
    )
    assert result.allowed is False


def test_filesystem_allowlist(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    ok = engine.check("read_file", {"path": "/reports/q1.txt"})
    assert ok.allowed is True

    bad = engine.check("read_file", {"path": "/system/shadow"})
    assert bad.allowed is False


def test_capability_engine_never_mutates_input(capabilities_dict):
    snapshot = dict(capabilities_dict)
    engine = CapabilityEngine(capabilities_dict)
    engine.check("send_email", {"to": "x@y.z"})
    assert capabilities_dict == snapshot


def test_capability_result_has_reason(capabilities_dict):
    engine = CapabilityEngine(capabilities_dict)
    result = engine.check("send_email", {})
    assert isinstance(result.reason, str)
    assert result.reason != ""