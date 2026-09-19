"""Audit, incidents and policies endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.dependencies import get_policy_engine
from app.ice.decision import Decision, RiskLevel
from app.schemas import (
    AuditEventView,
    AuditListResponse,
    IncidentListResponse,
    IncidentView,
    PolicyListResponse,
    PolicyView,
)
from app.storage.audit_repository import AuditRepository

router = APIRouter(prefix="/v1", tags=["audit"])


@router.get("/audit", response_model=AuditListResponse)
def list_audit(
    session_id: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> AuditListResponse:
    repo = AuditRepository()
    events, total = repo.list_audit_events(
        session_id=session_id,
        event_type=event_type,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return AuditListResponse(
        events=[
            AuditEventView(
                event_id=e["event_id"],
                timestamp=e["timestamp"],
                session_id=e["session_id"],
                event_type=e["event_type"],
                tool_name=e.get("tool_name"),
                decision=Decision(e["decision"]) if e.get("decision") else None,
                risk_level=RiskLevel(e["risk_level"]) if e.get("risk_level") else None,
                risk_score=e.get("risk_score"),
                reason_codes=e.get("reason_codes") or [],
                latency_ms=e.get("latency_ms"),
                detail=e.get("detail") or {},
            )
            for e in events
        ],
        total=total,
    )


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    session_id: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    decision: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    repo = AuditRepository()
    items, total = repo.list_incidents(
        session_id=session_id,
        risk_level=risk_level,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(
        incidents=[
            IncidentView(
                incident_id=i["incident_id"],
                created_at=i["created_at"],
                session_id=i["session_id"],
                user_intent=i["user_intent"],
                tool_name=i["tool_name"],
                tool_arguments=i["tool_arguments"],
                provenance=i["provenance"],
                risk_level=i["risk_level"],
                risk_score=i["risk_score"],
                decision=i["decision"],
                reason_codes=i["reason_codes"],
                explanation=i["explanation"],
                containment=i["containment"],
            )
            for i in items
        ],
        total=total,
    )


@router.get("/policies", response_model=PolicyListResponse)
def list_policies() -> PolicyListResponse:
    engine = get_policy_engine()
    return PolicyListResponse(
        policies=[PolicyView(name=p["name"], content=p["content"]) for p in engine.list_policy_files()]
    )