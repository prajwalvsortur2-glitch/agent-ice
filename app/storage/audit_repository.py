"""Persistence repository for Agent ICE audit, decisions, incidents, sessions.

This module is the ONLY supported way to read/write Agent ICE state to the
database from application code. Route handlers, the ICE controller, the
enforcement service, and the agent service all go through this class.

Design rules
------------
1.  No security decisions are made here. The repository records what the
    trusted engines decided; it does not decide anything itself.
2.  Every write uses an explicit transaction boundary (a short-lived session)
    so a failure cannot leave partial security state behind.
3.  Reads return detached, fully materialized domain objects (plain Python
    dicts / Pydantic models) — never SQLAlchemy ORM instances — so callers
    cannot accidentally trigger lazy loads after the session closes.
4.  Redaction is applied to `detail` payloads before persistence. Secrets
    (Authorization headers, tokens, passwords) are stripped centrally in
    `app.security.sanitizer.redact_secrets`.
5.  The repository is thread-safe: it does not hold a session; it opens one
    per operation using the shared session factory.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import delete, desc, func, select
from sqlalchemy.orm import Session

from app.ice.decision import Decision, RiskLevel
from app.models import (
    ContainmentInstruction,
    IntentAnchor,
    PolicyFinding,
    ProvenanceRef,
    RiskAssessment,
    SecurityDecision,
    ToolCall,
    TrustLevel,
)
from app.storage.database import get_session_factory
from app.storage.models import (
    ActionReceiptModel,
    AuditEventModel,
    IncidentModel,
    IntentModel,
    ProvenanceEventModel,
    SecurityDecisionModel,
    SessionModel,
    ToolRequestModel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime | None) -> datetime | None:
    """Return a timezone-aware UTC datetime for a value read from SQLite."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def canonical_arguments_hash(arguments: dict[str, Any]) -> str:
    """Deterministic SHA-256 over a tool's arguments.

    JSON serialization is sorted and compact so identical logical arguments
    always produce the same hash regardless of key insertion order.
    """
    payload = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_intent_hash(intent: IntentAnchor) -> str:
    """Deterministic SHA-256 over an IntentAnchor (used by receipts)."""
    payload = json.dumps(
        intent.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    """Best-effort secret redaction applied before persistence.

    The real redactor lives in `app.security.sanitizer`; we import it lazily
    so this module remains importable during early build-out.
    """
    if not detail:
        return {}
    try:
        from app.security.sanitizer import redact_secrets

        return redact_secrets(detail)
    except Exception:  # pragma: no cover - defensive; never break audit writes
        return dict(detail)


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------
class AuditRepository:
    """Read/write access for all Agent ICE persistence tables."""

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def _session(self) -> Session:
        return get_session_factory()()

    # ------------------------------------------------------------------
    # Sessions + Intent
    # ------------------------------------------------------------------
    def create_session(
        self,
        *,
        session_id: str,
        agent_name: str,
        intent: IntentAnchor,
        intent_hash: str,
    ) -> str:
        """Persist a new session and its immutable intent anchor."""
        with self._session() as db:
            session_row = SessionModel(
                id=session_id,
                agent_name=agent_name,
                status="active",
            )
            db.add(session_row)
            db.add(
                IntentModel(
                    session_id=session_id,
                    goal=intent.goal,
                    intent_hash=intent_hash,
                    allowed_tools=list(intent.allowed_tools),
                    allowed_operations=list(intent.allowed_operations),
                    restricted_operations=list(intent.restricted_operations),
                )
            )
            db.commit()
        logger.info("Session %s created (agent=%s)", session_id, agent_name)
        return session_id

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        with self._session() as db:
            row = db.get(SessionModel, session_id)
            if row is None:
                return None
            return {
                "session_id": row.id,
                "agent_name": row.agent_name,
                "status": row.status,
                "created_at": _ensure_utc(row.created_at),
            }

    def get_intent(self, session_id: str) -> Optional[IntentAnchor]:
        with self._session() as db:
            row = db.execute(
                select(IntentModel).where(IntentModel.session_id == session_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            return IntentAnchor(
                goal=row.goal,
                allowed_tools=list(row.allowed_tools or []),
                allowed_operations=list(row.allowed_operations or []),
                restricted_operations=list(row.restricted_operations or []),
            )

    def get_intent_hash(self, session_id: str) -> Optional[str]:
        with self._session() as db:
            row = db.execute(
                select(IntentModel.intent_hash).where(IntentModel.session_id == session_id)
            ).scalar_one_or_none()
            return row

    def close_session(self, session_id: str) -> None:
        with self._session() as db:
            row = db.get(SessionModel, session_id)
            if row is not None:
                row.status = "closed"
                db.commit()

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------
    def record_provenance(
        self,
        *,
        session_id: str,
        provenance: Sequence[ProvenanceRef],
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        if not provenance:
            return
        with self._session() as db:
            for ref in provenance:
                db.add(
                    ProvenanceEventModel(
                        session_id=session_id,
                        source_id=ref.source_id,
                        source_type=ref.source_type,
                        trust_level=ref.trust_level.value,
                        detail=_redact_detail(detail or {}),
                    )
                )
            db.commit()

    def list_provenance(self, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._session() as db:
            rows = db.execute(
                select(ProvenanceEventModel)
                .where(ProvenanceEventModel.session_id == session_id)
                .order_by(desc(ProvenanceEventModel.created_at))
                .limit(limit)
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "source_id": r.source_id,
                    "source_type": r.source_type,
                    "trust_level": r.trust_level,
                    "created_at": _ensure_utc(r.created_at),
                    "detail": r.detail or {},
                }
                for r in rows
            ]

    # ------------------------------------------------------------------
    # Tool requests
    # ------------------------------------------------------------------
    def record_tool_request(
        self,
        *,
        session_id: str,
        tool_call: ToolCall,
        request_id: Optional[str] = None,
    ) -> str:
        request_id = request_id or str(uuid.uuid4())
        arguments_hash = canonical_arguments_hash(tool_call.arguments)
        with self._session() as db:
            db.add(
                ToolRequestModel(
                    id=request_id,
                    session_id=session_id,
                    tool_name=tool_call.tool_name,
                    arguments=tool_call.arguments,
                    arguments_hash=arguments_hash,
                    provenance=[p.model_dump(mode="json") for p in tool_call.provenance],
                )
            )
            db.commit()
        return request_id

    def get_tool_request(self, request_id: str) -> Optional[dict[str, Any]]:
        with self._session() as db:
            row = db.get(ToolRequestModel, request_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "session_id": row.session_id,
                "created_at": _ensure_utc(row.created_at),
                "tool_name": row.tool_name,
                "arguments": row.arguments or {},
                "arguments_hash": row.arguments_hash,
                "provenance": row.provenance or [],
            }

    # ------------------------------------------------------------------
    # Security decisions
    # ------------------------------------------------------------------
    def record_security_decision(
        self,
        *,
        session_id: str,
        tool_request_id: str,
        decision: SecurityDecision,
        fast_path_result: Optional[dict[str, Any]] = None,
        deep_analysis_result: Optional[dict[str, Any]] = None,
    ) -> str:
        decision_id = str(uuid.uuid4())
        containment_payload: Optional[dict[str, Any]] = None
        if decision.containment is not None:
            containment_payload = decision.containment.model_dump(mode="json")

        with self._session() as db:
            db.add(
                SecurityDecisionModel(
                    id=decision_id,
                    session_id=session_id,
                    tool_request_id=tool_request_id,
                    decision=decision.decision.value,
                    risk_level=decision.risk.level.value,
                    risk_score=decision.risk.score,
                    reason_codes=list(decision.reason_codes),
                    explanation=decision.explanation or "",
                    fast_path_result=_redact_detail(fast_path_result or {}),
                    deep_analysis_result=(
                        _redact_detail(deep_analysis_result)
                        if deep_analysis_result is not None
                        else None
                    ),
                    containment=containment_payload,
                )
            )
            db.commit()
        return decision_id

    def get_security_decision(self, decision_id: str) -> Optional[dict[str, Any]]:
        with self._session() as db:
            row = db.get(SecurityDecisionModel, decision_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "session_id": row.session_id,
                "tool_request_id": row.tool_request_id,
                "created_at": _ensure_utc(row.created_at),
                "decision": row.decision,
                "risk_level": row.risk_level,
                "risk_score": row.risk_score,
                "reason_codes": row.reason_codes or [],
                "explanation": row.explanation,
                "fast_path_result": row.fast_path_result or {},
                "deep_analysis_result": row.deep_analysis_result,
                "containment": row.containment,
            }

    # ------------------------------------------------------------------
    # Action receipts
    # ------------------------------------------------------------------
    def record_receipt(
        self,
        *,
        receipt_id: str,
        session_id: str,
        inspection_id: str,
        intent_hash: str,
        tool_name: str,
        arguments_hash: str,
        resource: Optional[str],
        capability: Optional[str],
        decision: Decision,
        nonce: str,
        signature: str,
        expires_at: datetime,
    ) -> str:
        with self._session() as db:
            db.add(
                ActionReceiptModel(
                    id=receipt_id,
                    session_id=session_id,
                    inspection_id=inspection_id,
                    intent_hash=intent_hash,
                    tool_name=tool_name,
                    arguments_hash=arguments_hash,
                    resource=resource,
                    capability=capability,
                    decision=decision.value,
                    nonce=nonce,
                    signature=signature,
                    expires_at=expires_at,
                    consumed=False,
                )
            )
            db.commit()
        return receipt_id

    def get_receipt(self, receipt_id: str) -> Optional[dict[str, Any]]:
        with self._session() as db:
            row = db.get(ActionReceiptModel, receipt_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "session_id": row.session_id,
                "inspection_id": row.inspection_id,
                "created_at": _ensure_utc(row.created_at),
                "expires_at": _ensure_utc(row.expires_at),
                "intent_hash": row.intent_hash,
                "tool_name": row.tool_name,
                "arguments_hash": row.arguments_hash,
                "resource": row.resource,
                "capability": row.capability,
                "decision": row.decision,
                "nonce": row.nonce,
                "signature": row.signature,
                "consumed": row.consumed,
                "consumed_at": _ensure_utc(row.consumed_at),
            }

    def consume_receipt(self, receipt_id: str) -> bool:
        """Atomically mark a receipt consumed.

        Returns True if the receipt was pending and is now consumed.
        Returns False if it was already consumed (replay) or missing.
        """
        with self._session() as db:
            row = db.get(ActionReceiptModel, receipt_id)
            if row is None:
                return False
            if row.consumed:
                return False
            row.consumed = True
            row.consumed_at = _now()
            db.commit()
            return True

    # ------------------------------------------------------------------
    # Audit events
    # ------------------------------------------------------------------
    def record_audit_event(
        self,
        *,
        session_id: str,
        event_type: str,
        tool_name: Optional[str] = None,
        decision: Optional[Decision] = None,
        risk_level: Optional[RiskLevel] = None,
        risk_score: Optional[int] = None,
        reason_codes: Optional[Iterable[str]] = None,
        latency_ms: Optional[float] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self._session() as db:
            db.add(
                AuditEventModel(
                    id=event_id,
                    session_id=session_id,
                    event_type=event_type,
                    tool_name=tool_name,
                    decision=decision.value if decision else None,
                    risk_level=risk_level.value if risk_level else None,
                    risk_score=risk_score,
                    reason_codes=list(reason_codes or []),
                    latency_ms=latency_ms,
                    detail=_redact_detail(detail or {}),
                )
            )
            db.commit()
        return event_id

    def list_audit_events(
        self,
        *,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._session() as db:
            stmt = select(AuditEventModel)
            count_stmt = select(func.count(AuditEventModel.id))

            if session_id is not None:
                stmt = stmt.where(AuditEventModel.session_id == session_id)
                count_stmt = count_stmt.where(AuditEventModel.session_id == session_id)
            if event_type is not None:
                stmt = stmt.where(AuditEventModel.event_type == event_type)
                count_stmt = count_stmt.where(AuditEventModel.event_type == event_type)
            if decision is not None:
                stmt = stmt.where(AuditEventModel.decision == decision)
                count_stmt = count_stmt.where(AuditEventModel.decision == decision)

            total = int(db.execute(count_stmt).scalar_one())
            rows = db.execute(
                stmt.order_by(desc(AuditEventModel.created_at)).offset(offset).limit(limit)
            ).scalars().all()

            events = [
                {
                    "event_id": r.id,
                    "timestamp": _ensure_utc(r.created_at),
                    "session_id": r.session_id,
                    "event_type": r.event_type,
                    "tool_name": r.tool_name,
                    "decision": r.decision,
                    "risk_level": r.risk_level,
                    "risk_score": r.risk_score,
                    "reason_codes": r.reason_codes or [],
                    "latency_ms": r.latency_ms,
                    "detail": r.detail or {},
                }
                for r in rows
            ]
            return events, total

    def count_by_decision(self, session_id: Optional[str] = None) -> dict[str, int]:
        """Return counts of audit events grouped by decision value."""
        with self._session() as db:
            stmt = select(AuditEventModel.decision, func.count(AuditEventModel.id))
            if session_id is not None:
                stmt = stmt.where(AuditEventModel.session_id == session_id)
            stmt = stmt.where(AuditEventModel.decision.is_not(None)).group_by(
                AuditEventModel.decision
            )
            rows = db.execute(stmt).all()
            return {str(decision): int(count) for decision, count in rows}

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------
    def record_incident(
        self,
        *,
        session_id: str,
        user_intent: str,
        tool_call: ToolCall,
        risk: RiskAssessment,
        decision: Decision,
        reason_codes: Sequence[str],
        explanation: str,
        containment: Optional[ContainmentInstruction] = None,
        policy_findings: Optional[Sequence[PolicyFinding]] = None,
    ) -> str:
        incident_id = str(uuid.uuid4())
        containment_payload = containment.model_dump(mode="json") if containment else None

        combined_reasons = list(reason_codes)
        if policy_findings:
            for finding in policy_findings:
                if finding.reason_code not in combined_reasons:
                    combined_reasons.append(finding.reason_code)

        with self._session() as db:
            db.add(
                IncidentModel(
                    id=incident_id,
                    session_id=session_id,
                    user_intent=user_intent,
                    tool_name=tool_call.tool_name,
                    tool_arguments=tool_call.arguments,
                    provenance=[p.model_dump(mode="json") for p in tool_call.provenance],
                    risk_level=risk.level.value,
                    risk_score=risk.score,
                    decision=decision.value,
                    reason_codes=combined_reasons,
                    explanation=explanation,
                    containment=containment_payload,
                )
            )
            db.commit()
        logger.info(
            "Incident %s recorded (session=%s tool=%s decision=%s)",
            incident_id,
            session_id,
            tool_call.tool_name,
            decision.value,
        )
        return incident_id

    def list_incidents(
        self,
        *,
        session_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        decision: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._session() as db:
            stmt = select(IncidentModel)
            count_stmt = select(func.count(IncidentModel.id))

            if session_id is not None:
                stmt = stmt.where(IncidentModel.session_id == session_id)
                count_stmt = count_stmt.where(IncidentModel.session_id == session_id)
            if risk_level is not None:
                stmt = stmt.where(IncidentModel.risk_level == risk_level)
                count_stmt = count_stmt.where(IncidentModel.risk_level == risk_level)
            if decision is not None:
                stmt = stmt.where(IncidentModel.decision == decision)
                count_stmt = count_stmt.where(IncidentModel.decision == decision)

            total = int(db.execute(count_stmt).scalar_one())
            rows = db.execute(
                stmt.order_by(desc(IncidentModel.created_at)).offset(offset).limit(limit)
            ).scalars().all()

            incidents = [
                {
                    "incident_id": r.id,
                    "created_at": _ensure_utc(r.created_at),
                    "session_id": r.session_id,
                    "user_intent": r.user_intent,
                    "tool_name": r.tool_name,
                    "tool_arguments": r.tool_arguments or {},
                    "provenance": [
                        ProvenanceRef(
                            source_id=p.get("source_id", ""),
                            source_type=p.get("source_type", ""),
                            trust_level=TrustLevel(p.get("trust_level", "UNTRUSTED")),
                        )
                        for p in (r.provenance or [])
                    ],
                    "risk_level": RiskLevel(r.risk_level),
                    "risk_score": r.risk_score,
                    "decision": Decision(r.decision),
                    "reason_codes": r.reason_codes or [],
                    "explanation": r.explanation,
                    "containment": (
                        ContainmentInstruction(**r.containment) if r.containment else None
                    ),
                }
                for r in rows
            ]
            return incidents, total

    def get_incident(self, incident_id: str) -> Optional[dict[str, Any]]:
        with self._session() as db:
            row = db.get(IncidentModel, incident_id)
            if row is None:
                return None
            return {
                "incident_id": row.id,
                "created_at": _ensure_utc(row.created_at),
                "session_id": row.session_id,
                "user_intent": row.user_intent,
                "tool_name": row.tool_name,
                "tool_arguments": row.tool_arguments or {},
                "provenance": row.provenance or [],
                "risk_level": row.risk_level,
                "risk_score": row.risk_score,
                "decision": row.decision,
                "reason_codes": row.reason_codes or [],
                "explanation": row.explanation,
                "containment": row.containment,
            }

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def wipe_all(self) -> None:
        """Delete every row from every Agent ICE table.

        Used by reset scripts and integration tests. Never called from
        production code paths. Order matters because of FK constraints.
        """
        with self._session() as db:
            db.execute(delete(AuditEventModel))
            db.execute(delete(IncidentModel))
            db.execute(delete(ActionReceiptModel))
            db.execute(delete(SecurityDecisionModel))
            db.execute(delete(ToolRequestModel))
            db.execute(delete(ProvenanceEventModel))
            db.execute(delete(IntentModel))
            db.execute(delete(SessionModel))
            db.commit()
        logger.warning("Agent ICE database wiped.")

    def stats(self) -> dict[str, int]:
        """Return lightweight row counts for dashboards and health checks."""
        with self._session() as db:
            return {
                "sessions": int(db.execute(select(func.count(SessionModel.id))).scalar_one()),
                "intents": int(db.execute(select(func.count(IntentModel.id))).scalar_one()),
                "provenance_events": int(
                    db.execute(select(func.count(ProvenanceEventModel.id))).scalar_one()
                ),
                "tool_requests": int(
                    db.execute(select(func.count(ToolRequestModel.id))).scalar_one()
                ),
                "security_decisions": int(
                    db.execute(select(func.count(SecurityDecisionModel.id))).scalar_one()
                ),
                "action_receipts": int(
                    db.execute(select(func.count(ActionReceiptModel.id))).scalar_one()
                ),
                "audit_events": int(
                    db.execute(select(func.count(AuditEventModel.id))).scalar_one()
                ),
                "incidents": int(db.execute(select(func.count(IncidentModel.id))).scalar_one()),
            }