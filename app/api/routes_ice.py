"""Session, inspection, execution, approval and restriction endpoints."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings
from app.dependencies import (
    get_agent_service,
    get_ice_controller,
    get_settings_dep,
)
from app.ice.decision import Decision, ReasonCode
from app.models import IntentAnchor
from app.schemas import (
    ActionReceiptView,
    ApproveRequest,
    ApproveResponse,
    ExecuteRequest,
    ExecuteResponse,
    InspectRequest,
    InspectResponse,
    RestrictRequest,
    RestrictResponse,
    SessionCreateRequest,
    SessionCreateResponse,
)
from app.storage.audit_repository import AuditRepository
from app.telemetry.events import emit_security_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["ice"])


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
@router.post("/session", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    body: SessionCreateRequest,
    settings: Settings = Depends(get_settings_dep),
) -> SessionCreateResponse:
    agent = get_agent_service()
    repo = AuditRepository()

    try:
        anchor: IntentAnchor
        anchor, intent_hash = agent.build_intent(body.user_intent)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid intent: {exc}") from exc

    session_id = str(uuid.uuid4())
    repo.create_session(
        session_id=session_id,
        agent_name=body.agent_name,
        intent=anchor,
        intent_hash=intent_hash,
    )

    emit_security_event(
        event_type="session_created",
        session_id=session_id,
        payload={"agent_name": body.agent_name, "goal": anchor.goal},
    )

    return SessionCreateResponse(
        session_id=session_id,
        intent=anchor,
        intent_hash=intent_hash,
        agent_name=body.agent_name,
        created_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------
@router.post("/inspect", response_model=InspectResponse)
def inspect_tool_call(body: InspectRequest) -> InspectResponse:
    controller = get_ice_controller()

    outcome = controller.inspect(session_id=body.session_id, tool_call=body.tool_call)
    model = outcome.decision

    receipt_view: ActionReceiptView | None = None
    if model.decision == Decision.ALLOW and model.receipt_token and model.receipt_id:
        receipt = AuditRepository().get_receipt(model.receipt_id)
        expires_at = receipt["expires_at"] if receipt else datetime.now(timezone.utc)
        receipt_view = ActionReceiptView(
            receipt_id=model.receipt_id,
            token=model.receipt_token,
            expires_at=expires_at,
        )

    emit_security_event(
        event_type="inspect",
        session_id=body.session_id,
        payload={
            "tool_name": body.tool_call.tool_name,
            "decision": model.decision.value,
            "risk_level": model.risk.level.value,
            "risk_score": model.risk.score,
        },
    )

    return InspectResponse(
        inspection_id=model.inspection_id,
        decision=model.decision,
        risk=model.risk,
        reason_codes=model.reason_codes,
        explanation=model.explanation,
        policy_findings=model.policy_findings,
        containment=model.containment,
        receipt=receipt_view,
        review_id=outcome.review_id,
        latency_ms=outcome.latency_ms,
    )


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------
@router.post("/execute", response_model=ExecuteResponse)
def execute_tool_call(body: ExecuteRequest) -> ExecuteResponse:
    agent = get_agent_service()
    outcome = agent.execute_authorized(
        session_id=body.session_id,
        receipt_token=body.receipt_token,
        tool_call=body.tool_call,
    )

    emit_security_event(
        event_type="execution" if outcome.success else "execution_denied",
        session_id=body.session_id,
        payload={
            "tool_name": body.tool_call.tool_name,
            "success": outcome.success,
            "error": outcome.error,
        },
        severity="INFO" if outcome.success else "WARNING",
    )

    return ExecuteResponse(
        success=outcome.success,
        executed_tool=outcome.executed_tool or body.tool_call.tool_name,
        result=outcome.result,
        error=outcome.error,
        audit_event_id=outcome.audit_event_id,
        latency_ms=outcome.latency_ms,
    )


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------
@router.post("/approve", response_model=ApproveResponse)
def approve_review(body: ApproveRequest) -> ApproveResponse:
    controller = get_ice_controller()
    repo = AuditRepository()

    review = controller._enforcement.get_review(body.review_id)  # noqa: SLF001 — intentional: enforcement is the owner of pending reviews
    if review is None:
        raise HTTPException(status_code=404, detail="unknown or expired review")
    if review.session_id != body.session_id:
        raise HTTPException(status_code=403, detail="review does not belong to this session")

    controller._enforcement.pop_review(body.review_id)  # noqa: SLF001

    if not body.approved:
        repo.record_audit_event(
            session_id=body.session_id,
            event_type="rejection",
            tool_name=review.tool_call.tool_name,
            decision=Decision.BLOCK,
            risk_level=review.risk.level,
            risk_score=review.risk.score,
            reason_codes=[ReasonCode.APPROVAL_REJECTED],
            detail={"review_id": body.review_id, "note": body.note},
        )
        emit_security_event(
            event_type="rejection",
            session_id=body.session_id,
            payload={"review_id": body.review_id, "tool": review.tool_call.tool_name},
            severity="WARNING",
        )
        return ApproveResponse(
            review_id=body.review_id,
            approved=False,
            receipt=None,
            decision=Decision.BLOCK,
        )

    # Approval: issue a receipt bound to the exact tool call that was
    # inspected. The user has now explicitly authorized it.
    intent_hash = repo.get_intent_hash(body.session_id) or ""
    issued = controller._receipts.issue(  # noqa: SLF001
        session_id=body.session_id,
        inspection_id=review.inspection_id,
        intent_hash=intent_hash,
        tool_call=review.tool_call,
        resource=review.resource,
        capability=review.capability,
        decision=Decision.ALLOW,
    )
    repo.record_receipt(
        receipt_id=issued.receipt_id,
        session_id=body.session_id,
        inspection_id=review.inspection_id,
        intent_hash=intent_hash,
        tool_name=review.tool_call.tool_name,
        arguments_hash=repo.canonical_arguments_hash(review.tool_call.arguments),
        resource=review.resource,
        capability=review.capability,
        decision=Decision.ALLOW,
        nonce=issued.token[:16],
        signature=issued.token[-64:],
        expires_at=issued.expires_at,
    )

    repo.record_audit_event(
        session_id=body.session_id,
        event_type="approval",
        tool_name=review.tool_call.tool_name,
        decision=Decision.ALLOW,
        risk_level=review.risk.level,
        risk_score=review.risk.score,
        reason_codes=[ReasonCode.APPROVAL_GRANTED],
        detail={"review_id": body.review_id, "note": body.note},
    )
    emit_security_event(
        event_type="approval",
        session_id=body.session_id,
        payload={"review_id": body.review_id, "tool": review.tool_call.tool_name},
    )

    return ApproveResponse(
        review_id=body.review_id,
        approved=True,
        receipt=ActionReceiptView(
            receipt_id=issued.receipt_id,
            token=issued.token,
            expires_at=issued.expires_at,
        ),
        decision=Decision.ALLOW,
    )


# ---------------------------------------------------------------------------
# Restrict
# ---------------------------------------------------------------------------
@router.post("/restrict", response_model=RestrictResponse)
def apply_restriction(body: RestrictRequest) -> RestrictResponse:
    controller = get_ice_controller()
    repo = AuditRepository()

    pending = controller._enforcement.pop_restriction(body.inspection_id)  # noqa: SLF001
    if pending is None:
        raise HTTPException(status_code=404, detail="unknown or expired restriction")
    if pending.session_id != body.session_id:
        raise HTTPException(status_code=403, detail="restriction does not belong to this session")

    if not body.accept:
        repo.record_audit_event(
            session_id=body.session_id,
            event_type="rejection",
            tool_name=pending.tool_call.tool_name,
            decision=Decision.BLOCK,
            reason_codes=[ReasonCode.APPROVAL_REJECTED],
            detail={"inspection_id": body.inspection_id},
        )
        return RestrictResponse(
            inspection_id=body.inspection_id,
            decision=Decision.BLOCK,
            containment=None,
            receipt=None,
        )

    # Issue a receipt for the *replacement* tool call — never the original.
    replacement_call = type(pending.tool_call)(
        tool_name=pending.containment.replacement_tool,
        arguments=pending.containment.replacement_arguments,
        provenance=list(pending.tool_call.provenance),
    )
    intent_hash = repo.get_intent_hash(body.session_id) or ""
    issued = controller._receipts.issue(  # noqa: SLF001
        session_id=body.session_id,
        inspection_id=pending.inspection_id,
        intent_hash=intent_hash,
        tool_call=replacement_call,
        resource=pending.resource,
        capability=pending.capability,
        decision=Decision.RESTRICT,
    )
    repo.record_receipt(
        receipt_id=issued.receipt_id,
        session_id=body.session_id,
        inspection_id=pending.inspection_id,
        intent_hash=intent_hash,
        tool_name=replacement_call.tool_name,
        arguments_hash=repo.canonical_arguments_hash(replacement_call.arguments),
        resource=pending.resource,
        capability=pending.capability,
        decision=Decision.RESTRICT,
        nonce=issued.token[:16],
        signature=issued.token[-64:],
        expires_at=issued.expires_at,
    )

    repo.record_audit_event(
        session_id=body.session_id,
        event_type="restriction",
        tool_name=replacement_call.tool_name,
        decision=Decision.RESTRICT,
        reason_codes=[ReasonCode.RESTRICTED_TO_SAFE_ACTION],
        detail={
            "inspection_id": body.inspection_id,
            "original_tool": pending.tool_call.tool_name,
            "replacement_tool": replacement_call.tool_name,
        },
    )

    return RestrictResponse(
        inspection_id=body.inspection_id,
        decision=Decision.RESTRICT,
        containment=pending.containment,
        receipt=ActionReceiptView(
            receipt_id=issued.receipt_id,
            token=issued.token,
            expires_at=issued.expires_at,
        ),
    )