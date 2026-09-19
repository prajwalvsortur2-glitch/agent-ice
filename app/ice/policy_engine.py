"""Deterministic policy engine.

Policy evaluation is fully deterministic and never delegates to the LLM.
Policies live in `policies/*.yaml`. Missing or malformed policy files cause
the engine to fall back to conservative defaults and log loudly — it never
fails open.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.ice.decision import ReasonCode, RiskLevel
from app.models import PolicyFinding, ToolCall, TrustLevel
from app.security.dangerous_patterns import (
    classify_operation_keywords,
    is_sensitive_resource,
)
from app.security.validators import (
    email_domain,
    is_external_email,
    is_safe_url,
)

logger = logging.getLogger(__name__)


# Fallback configuration. Kept intentionally conservative.
_FALLBACK_POLICY: dict[str, Any] = {
    "tools": {
        "allowlist": ["read_email", "read_file", "query_database", "send_email", "delete_record"],
        "high_impact": ["send_email", "delete_record"],
    },
    "resources": {
        "sensitive_markers": ["customer", "billing", "payroll", "credential", "secret"],
        "path_allowlist": ["data/fixtures/files", "reports"],
    },
    "network": {
        "domain_allowlist": ["company.local", "internal.company.local"],
    },
    "email": {
        "internal_domains": ["company.local"],
    },
    "risk": {
        "thresholds": {"low_max": 24, "medium_max": 49, "high_max": 79},
    },
}


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    reason_codes: list[str]
    matched_rules: list[str]


class PolicyEngine:
    def __init__(
        self,
        settings: Settings | dict[str, Any] | None = None,
        policies_dir: str | None = None,
    ) -> None:
        if isinstance(settings, dict):
            self._settings = Settings()
            self._dir = Path(policies_dir or ".")
            self._legacy_policy = dict(settings)
            self._loaded: dict[str, dict[str, Any]] = {}
            return
        self._settings = settings or Settings()
        self._dir = Path(policies_dir or self._settings.policies_dir)
        self._loaded: dict[str, dict[str, Any]] = {}
        self._legacy_policy = {}
        self._load_all()

    @classmethod
    def from_directory(cls, path: str | Path) -> "PolicyEngine":
        policy_dir = Path(path)
        if not policy_dir.exists() or not policy_dir.is_dir():
            raise FileNotFoundError(f"Policy directory does not exist: {policy_dir}")
        return cls(Settings(), str(policy_dir))

    # ------------------------------------------------------------------
    def _load_all(self) -> None:
        for filename, key in (
            ("default_policy.yaml", "default"),
            ("tools.yaml", "tools"),
            ("resources.yaml", "resources"),
            ("permissions.yaml", "permissions"),
            ("risk_thresholds.yaml", "risk"),
        ):
            path = self._dir / filename
            if not path.exists():
                logger.warning("policy file %s not found; using defaults", path)
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if isinstance(data, dict):
                    self._loaded[key] = data
            except (OSError, yaml.YAMLError) as exc:
                logger.error("failed to load policy %s: %s", path, exc)

    def reload(self) -> None:
        self._loaded.clear()
        self._load_all()

    def _get(self, key: str, default: Any) -> Any:
        return self._loaded.get(key, {}).get("policy", default)

    def _section(self, name: str) -> dict[str, Any]:
        """Return the merged configuration for a logical section."""
        merged: dict[str, Any] = dict(_FALLBACK_POLICY.get(name, {}))
        section = self._loaded.get(name, {})
        if isinstance(section, dict):
            merged.update({k: v for k, v in section.items() if k != "policy"})
        return merged

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def list_policy_files(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                content = {"_error": str(exc)}
            out.append({"name": path.name, "content": content})
        return out

    def evaluate(
        self,
        *,
        tool_call: ToolCall | None = None,
        resource: str | None = None,
        intent_goal: str = "",
        request: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[PolicyFinding] | PolicyResult:
        if request is not None:
            legacy_tool = str(request.get("tool", ""))
            legacy_args = request.get("arguments", {}) or {}
            legacy_context = context or {}
            reason_codes: list[str] = []
            matched_rules: list[str] = []
            if not legacy_tool:
                return PolicyResult(decision="BLOCK", reason_codes=[ReasonCode.UNKNOWN_TOOL], matched_rules=["empty-tool"])
            if not legacy_context.get("capability_granted", True):
                reason_codes.append(ReasonCode.CAPABILITY_DENIED)
                matched_rules.append("deny-delete-without-capability")
                return PolicyResult(decision="BLOCK", reason_codes=reason_codes, matched_rules=matched_rules)
            if legacy_tool == "send_email":
                dest = str((legacy_args or {}).get("to", ""))
                if legacy_context.get("data_classification") == "sensitive" or legacy_context.get("destination_external"):
                    if not legacy_context.get("destination_allowlisted", False):
                        reason_codes.append(ReasonCode.EXFILTRATION_BLOCKED)
                        matched_rules.append("external-sensitive-transfer")
                        return PolicyResult(decision="BLOCK", reason_codes=reason_codes, matched_rules=matched_rules)
                if legacy_context.get("destination_external") is True and not legacy_context.get("destination_allowlisted", False):
                    reason_codes.append(ReasonCode.EXFILTRATION_BLOCKED)
                    matched_rules.append("external-destination-default")
                    return PolicyResult(decision="BLOCK", reason_codes=reason_codes, matched_rules=matched_rules)
            if legacy_tool in {"send_email", "delete_record"}:
                reason_codes.append(ReasonCode.HIGH_IMPACT_ACTION)
                matched_rules.append("high-impact-default")
                return PolicyResult(decision="BLOCK", reason_codes=reason_codes, matched_rules=matched_rules)
            return PolicyResult(decision="ALLOW", reason_codes=[ReasonCode.ALLOWED], matched_rules=["default-allow"])

        if tool_call is None:
            raise ValueError("tool_call is required when request is omitted")
        findings: list[PolicyFinding] = []
        findings.extend(self._check_tool_allowlist(tool_call))
        findings.extend(self._check_high_impact(tool_call))
        findings.extend(self._check_resource(tool_call, resource))
        findings.extend(self._check_external_destination(tool_call))
        findings.extend(self._check_path_allowlist(tool_call))
        findings.extend(self._check_url_allowlist(tool_call))
        findings.extend(self._check_destructive(tool_call))
        return findings

    # ------------------------------------------------------------------
    # Rule implementations
    # ------------------------------------------------------------------
    def _check_tool_allowlist(self, tool_call: ToolCall) -> list[PolicyFinding]:
        tools = self._section("tools")
        allowlist = set(tools.get("allowlist", []))
        if tool_call.tool_name not in allowlist:
            return [
                PolicyFinding(
                    rule_id="tools.allowlist",
                    reason_code=ReasonCode.TOOL_NOT_ALLOWED,
                    severity=RiskLevel.CRITICAL,
                    message=f"tool {tool_call.tool_name!r} is not on the allowlist",
                )
            ]
        return []

    def _check_high_impact(self, tool_call: ToolCall) -> list[PolicyFinding]:
        tools = self._section("tools")
        high_impact = set(tools.get("high_impact", []))
        if tool_call.tool_name in high_impact:
            return [
                PolicyFinding(
                    rule_id="tools.high_impact",
                    reason_code=ReasonCode.HIGH_IMPACT_ACTION,
                    severity=RiskLevel.HIGH,
                    message=f"tool {tool_call.tool_name!r} is classified as high-impact",
                )
            ]
        return []

    def _check_resource(self, tool_call: ToolCall, resource: str | None) -> list[PolicyFinding]:
        if not resource:
            return []
        findings: list[PolicyFinding] = []
        if is_sensitive_resource(resource):
            findings.append(
                PolicyFinding(
                    rule_id="resources.sensitive",
                    reason_code=ReasonCode.SENSITIVE_RESOURCE,
                    severity=RiskLevel.HIGH,
                    message=f"resource {resource!r} is classified as sensitive",
                )
            )
        # Sensitive resource accessed with untrusted provenance → policy violation.
        if any(p.trust_level == TrustLevel.UNTRUSTED for p in tool_call.provenance):
            findings.append(
                PolicyFinding(
                    rule_id="resources.untrusted_access",
                    reason_code=ReasonCode.POLICY_VIOLATION,
                    severity=RiskLevel.CRITICAL,
                    message=(
                        f"sensitive resource {resource!r} is being accessed based on "
                        f"untrusted provenance"
                    ),
                )
            )
        return findings

    def _check_external_destination(self, tool_call: ToolCall) -> list[PolicyFinding]:
        if tool_call.tool_name != "send_email":
            return []
        to = str(tool_call.arguments.get("to", ""))
        if not to:
            return []
        email_section = self._section("email")
        internal = email_section.get("internal_domains", ["company.local"])
        if is_external_email(to, internal):
            return [
                PolicyFinding(
                    rule_id="email.external_destination",
                    reason_code=ReasonCode.EXTERNAL_DESTINATION_DENIED,
                    severity=RiskLevel.CRITICAL,
                    message=(
                        f"email recipient {to!r} (domain {email_domain(to)!r}) is external"
                    ),
                )
            ]
        return []

    def _check_path_allowlist(self, tool_call: ToolCall) -> list[PolicyFinding]:
        if tool_call.tool_name != "read_file":
            return []
        path = str(tool_call.arguments.get("path", ""))
        if not path:
            return []
        resources = self._section("resources")
        allowlist = resources.get("path_allowlist", [])
        if allowlist and not any(path.startswith(prefix) for prefix in allowlist):
            return [
                PolicyFinding(
                    rule_id="resources.path_allowlist",
                    reason_code=ReasonCode.RESOURCE_DENIED,
                    severity=RiskLevel.HIGH,
                    message=f"path {path!r} is outside the allowed roots",
                )
            ]
        return []

    def _check_url_allowlist(self, tool_call: ToolCall) -> list[PolicyFinding]:
        # Applicable to any tool that takes a `url` argument.
        url = tool_call.arguments.get("url")
        if not isinstance(url, str) or not url:
            return []
        network = self._section("network")
        allowed_domains = network.get("domain_allowlist", [])
        ok, reason = is_safe_url(url, allowed_domains=allowed_domains)
        if not ok:
            return [
                PolicyFinding(
                    rule_id="network.domain_allowlist",
                    reason_code=ReasonCode.EXTERNAL_DESTINATION_DENIED,
                    severity=RiskLevel.CRITICAL,
                    message=f"url {url!r} rejected: {reason}",
                )
            ]
        return []

    def _check_destructive(self, tool_call: ToolCall) -> list[PolicyFinding]:
        # Classify the tool name + stringified arguments.
        strings = [tool_call.tool_name]
        for value in _iter_strings(tool_call.arguments):
            strings.append(value)
        classified = classify_operation_keywords(*strings)
        if classified["destructive"]:
            return [
                PolicyFinding(
                    rule_id="operations.destructive",
                    reason_code=ReasonCode.DESTRUCTIVE_OPERATION,
                    severity=RiskLevel.CRITICAL,
                    message=f"tool {tool_call.tool_name!r} appears to perform a destructive operation",
                )
            ]
        return []

    # ------------------------------------------------------------------
    def risk_thresholds(self) -> dict[str, int]:
        risk = self._section("risk")
        thresholds = risk.get("thresholds") or {}
        return {
            "low_max": int(thresholds.get("low_max", 24)),
            "medium_max": int(thresholds.get("medium_max", 49)),
            "high_max": int(thresholds.get("high_max", 79)),
        }


def _iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _iter_strings(v)