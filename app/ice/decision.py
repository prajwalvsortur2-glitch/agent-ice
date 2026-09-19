"""Decision and risk primitives shared across all ICE engines.

The four decision types are fixed:
    ALLOW | REVIEW | RESTRICT | BLOCK
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


@dataclass
class InspectionResult:
    """Compatibility result object for the legacy inspection API."""

    decision: "Decision | Any"
    risk_level: str
    risk_score: float
    reason_codes: list[str] = field(default_factory=list)
    receipt: Any | None = None
    containment: Any | None = None
    inspection_id: str = ""
    review_id: Optional[str] = None
    latency_ms: float = 0.0


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    RESTRICT = "RESTRICT"
    BLOCK = "BLOCK"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_score(cls, score: int, thresholds: dict[str, int] | None = None) -> "RiskLevel":
        """Map a 0..100 score to a risk level using configurable thresholds."""
        t = thresholds or {"low_max": 24, "medium_max": 49, "high_max": 79}
        if score <= t["low_max"]:
            return cls.LOW
        if score <= t["medium_max"]:
            return cls.MEDIUM
        if score <= t["high_max"]:
            return cls.HIGH
        return cls.CRITICAL


class ReasonCode:
    """Stable string codes attached to every decision.

    These are consumed by the UI, tests, and audit exports. Never invent
    ad-hoc strings elsewhere — add them here.
    """

    # Capability
    CAPABILITY_DENIED = "CAPABILITY_DENIED"
    CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"

    # Tool
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"

    # Intent
    INTENT_MISMATCH_HIGH = "INTENT_MISMATCH_HIGH"
    INTENT_MISMATCH_MEDIUM = "INTENT_MISMATCH_MEDIUM"

    # Provenance
    UNTRUSTED_PROVENANCE = "UNTRUSTED_PROVENANCE"
    PROVENANCE_MANIPULATION = "PROVENANCE_MANIPULATION"

    # Policy / resource
    RESOURCE_DENIED = "RESOURCE_DENIED"
    EXTERNAL_DESTINATION_DENIED = "EXTERNAL_DESTINATION_DENIED"
    HIGH_IMPACT_ACTION = "HIGH_IMPACT_ACTION"
    DESTRUCTIVE_OPERATION = "DESTRUCTIVE_OPERATION"
    SENSITIVE_RESOURCE = "SENSITIVE_RESOURCE"

    # Validation
    PATH_TRAVERSAL = "PATH_TRAVERSAL"
    SSRF_BLOCKED = "SSRF_BLOCKED"
    COMMAND_INJECTION = "COMMAND_INJECTION"
    SQL_INJECTION = "SQL_INJECTION"
    ARGUMENT_SCHEMA_INVALID = "ARGUMENT_SCHEMA_INVALID"

    # Receipt
    RECEIPT_MISSING = "RECEIPT_MISSING"
    RECEIPT_INVALID = "RECEIPT_INVALID"
    RECEIPT_EXPIRED = "RECEIPT_EXPIRED"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"
    RECEIPT_REPLAY = "RECEIPT_REPLAY"

    # Review / restrict
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    RESTRICTED_TO_SAFE_ACTION = "RESTRICTED_TO_SAFE_ACTION"
    EXFILTRATION_BLOCKED = "EXFILTRATION_BLOCKED"

    # LLM
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_MALFORMED = "LLM_MALFORMED"
    LLM_ALIGNMENT_LOW = "LLM_ALIGNMENT_LOW"

    # Generic
    POLICY_VIOLATION = "POLICY_VIOLATION"
    FAIL_CLOSED = "FAIL_CLOSED"
    ALLOWED = "ALLOWED"