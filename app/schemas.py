"""HTTP API contract for the Agent ICE backend.

These models define what clients send and receive. They intentionally wrap the
internal domain models in `app.models` so the internal representation can
evolve without breaking the API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.ice.decision import Decision, RiskLevel
from app.models import (
    ContainmentInstruction,
    IntentAnchor,
    PolicyFinding,
    ProvenanceRef,
    RiskAssessment,
    ToolCall,
)


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_intent: str = Field(..., min_length=1, max_length=4000)
    agent_name: str = Field(default="qwen-agent", max_length=128)


class SessionCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    intent: IntentAnchor
    intent_hash: str
    agent_name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------
class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    tool_call: ToolCall


class ActionReceiptView(BaseModel):
    """The token the client must pass back to /v1/execute on ALLOW."""

    model_config = ConfigDict(extra="forbid")
    receipt_id: str
    token: str
    expires_at: datetime


class InspectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inspection_id: str
    decision: Decision
    risk: RiskAssessment
    reason_codes: list[str]
    explanation: str
    policy_findings: list[PolicyFinding] = Field(default_factory=list)
    containment: Optional[ContainmentInstruction] = None
    receipt: Optional[ActionReceiptView] = None
    review_id: Optional[str] = None
    latency_ms: float


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
class ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    receipt_token: str
    tool_call: ToolCall


class ExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool
    executed_tool: str
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    audit_event_id: Optional[str] = None
    latency_ms: float


# ---------------------------------------------------------------------------
# Approve / Restrict
# ---------------------------------------------------------------------------
class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    review_id: str
    approved: bool
    note: Optional[str] = Field(default=None, max_length=1000)


class ApproveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str
    approved: bool
    receipt: Optional[ActionReceiptView] = None
    decision: Decision


class RestrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    inspection_id: str
    accept: bool = True


class RestrictResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inspection_id: str
    decision: Decision
    containment: Optional[ContainmentInstruction] = None
    receipt: Optional[ActionReceiptView] = None


# ---------------------------------------------------------------------------
# Audit / Incidents / Policies
# ---------------------------------------------------------------------------
class AuditEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    timestamp: datetime
    session_id: str
    event_type: str
    tool_name: Optional[str] = None
    decision: Optional[Decision] = None
    risk_level: Optional[RiskLevel] = None
    risk_score: Optional[int] = None
    reason_codes: list[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[AuditEventView]
    total: int


class IncidentView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str
    created_at: datetime
    session_id: str
    user_intent: str
    tool_name: str
    tool_arguments: dict[str, Any]
    provenance: list[ProvenanceRef]
    risk_level: RiskLevel
    risk_score: int
    decision: Decision
    reason_codes: list[str]
    explanation: str
    containment: Optional[ContainmentInstruction] = None


class IncidentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incidents: list[IncidentView]
    total: int


class PolicyView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    content: dict[str, Any]


class PolicyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policies: list[PolicyView]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    app_env: str
    version: str
    components: dict[str, str]
    fail_closed: bool


class OllamaHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reachable: bool
    base_url: str
    model: str
    model_available: bool
    detail: Optional[str] = None