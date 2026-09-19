"""Agent-only conveniences.

The agent has no privileged endpoint here. This router exists to expose the
agent's read-only view of its environment: available tools, current intent,
and a deterministic "propose" helper that returns an inspection result
without executing anything.

Nothing in this router can cause a tool to execute. Execution lives in
`app/api/routes_ice.py` and always requires a valid receipt.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_agent_service
from app.models import ProvenanceRef, ToolCall, TrustLevel
from app.schemas import (
    InspectResponse,
    SessionCreateResponse,
)
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/v1/agent", tags=["agent"])


class ProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    tool_name: str
    arguments: dict = {}
    untrusted: bool = False


@router.post("/propose", response_model=InspectResponse)
def propose(body: ProposeRequest) -> InspectResponse:
    agent = get_agent_service()
    provenance = (
        [ProvenanceRef(source_id="external", source_type="external_tool_result", trust_level=TrustLevel.UNTRUSTED)]
        if body.untrusted
        else [ProvenanceRef(source_id="user_prompt", source_type="user_prompt", trust_level=TrustLevel.TRUSTED)]
    )
    tool_call = ToolCall(
        tool_name=body.tool_name,
        arguments=body.arguments,
        provenance=provenance,
    )
    proposal = agent.propose(session_id=body.session_id, tool_call=tool_call)
    assert proposal.inspection is not None
    m = proposal.inspection.decision
    return InspectResponse(
        inspection_id=m.inspection_id,
        decision=m.decision,
        risk=m.risk,
        reason_codes=m.reason_codes,
        explanation=m.explanation,
        policy_findings=m.policy_findings,
        containment=m.containment,
        receipt=None,
        review_id=proposal.inspection.review_id,
        latency_ms=proposal.inspection.latency_ms,
    )