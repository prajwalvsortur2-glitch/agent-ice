"""Internal domain models used across Agent ICE engines.

Kept separate from:
  - `app.schemas`        — HTTP request/response contract
  - `app.storage.models` — SQLAlchemy persistence tables

This separation keeps transport and persistence concerns out of the security
logic. All models here are Pydantic v2 models validated on construction.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ice.decision import Decision, RiskLevel


class TrustLevel(str, Enum):
    """Trust classification for any piece of external content or data."""

    TRUSTED = "TRUSTED"
    RESTRICTED = "RESTRICTED"
    UNTRUSTED = "UNTRUSTED"


class ProvenanceRef(BaseModel):
    """A single provenance reference attached to a tool call."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=256)
    source_type: str = Field(..., min_length=1, max_length=64)
    trust_level: TrustLevel


class IntentAnchor(BaseModel):
    """Immutable, structured representation of the original user goal.

    Produced at session creation. Later instructions — especially from
    untrusted content — must not silently replace it.
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(..., min_length=1, max_length=2000)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=list)
    restricted_operations: list[str] = Field(default_factory=list)

    @field_validator("allowed_tools", "allowed_operations", "restricted_operations")
    @classmethod
    def _dedupe_and_normalize(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in v:
            s = item.strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out


class ToolCall(BaseModel):
    """A proposed tool invocation from the agent."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(..., min_length=1, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    provenance: list[ProvenanceRef] = Field(default_factory=list)

    def has_untrusted_provenance(self) -> bool:
        return any(p.trust_level == TrustLevel.UNTRUSTED for p in self.provenance)

    def has_restricted_provenance(self) -> bool:
        return any(p.trust_level == TrustLevel.RESTRICTED for p in self.provenance)


class PolicyFinding(BaseModel):
    """A single deterministic policy finding produced by the policy engine."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    reason_code: str
    severity: RiskLevel
    message: str


class RiskAssessment(BaseModel):
    """Explainable risk result produced by the risk engine."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    level: RiskLevel
    signals: dict[str, int] = Field(default_factory=dict)
    explanation: str


class DriftAssessment(BaseModel):
    """Intent drift result produced by the drift engine."""

    model_config = ConfigDict(extra="forbid")

    alignment: str  # LOW | MEDIUM | HIGH
    confidence: float = Field(ge=0.0, le=1.0)
    risk_delta: int = Field(ge=-100, le=100)
    recommended_action: Decision | None = None
    reasons: list[str] = Field(default_factory=list)
    source: str = "deterministic"  # "deterministic" | "qwen"
    raw_model_output: str | None = None


class ContainmentInstruction(BaseModel):
    """Instruction emitted when the decision is RESTRICT.

    The trusted executor MUST perform the downgrade — not the LLM.
    """

    model_config = ConfigDict(extra="forbid")

    original_tool: str
    replacement_tool: str
    replacement_arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str


class SecurityDecision(BaseModel):
    """Final, authoritative decision emitted by Agent ICE."""

    model_config = ConfigDict(extra="forbid")

    decision: Decision
    risk: RiskAssessment
    drift: DriftAssessment | None = None
    policy_findings: list[PolicyFinding] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    explanation: str = ""
    containment: ContainmentInstruction | None = None
    review_required: bool = False
    receipt_token: str | None = None
    receipt_id: str | None = None
    inspection_id: str
    review_id: str | None = None