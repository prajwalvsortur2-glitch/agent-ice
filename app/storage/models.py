"""SQLAlchemy ORM models for Agent ICE persistence.

Tables:
    sessions
    intents
    provenance_events
    tool_requests
    security_decisions
    action_receipts
    audit_events
    incidents
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    agent_name: Mapped[str] = mapped_column(String(128), default="qwen-agent")
    status: Mapped[str] = mapped_column(String(32), default="active")

    intent: Mapped["IntentModel"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    tool_requests: Mapped[list["ToolRequestModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEventModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["IncidentModel"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class IntentModel(Base):
    __tablename__ = "intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    goal: Mapped[str] = mapped_column(Text)
    intent_hash: Mapped[str] = mapped_column(String(64), index=True)
    allowed_tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    allowed_operations: Mapped[list[str]] = mapped_column(JSON, default=list)
    restricted_operations: Mapped[list[str]] = mapped_column(JSON, default=list)

    session: Mapped[SessionModel] = relationship(back_populates="intent")


class ProvenanceEventModel(Base):
    __tablename__ = "provenance_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(256))
    source_type: Mapped[str] = mapped_column(String(64))
    trust_level: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ToolRequestModel(Base):
    __tablename__ = "tool_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tool_name: Mapped[str] = mapped_column(String(128), index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    arguments_hash: Mapped[str] = mapped_column(String(64))
    provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    session: Mapped[SessionModel] = relationship(back_populates="tool_requests")


class SecurityDecisionModel(Base):
    __tablename__ = "security_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    tool_request_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    decision: Mapped[str] = mapped_column(String(16), index=True)
    risk_level: Mapped[str] = mapped_column(String(16))
    risk_score: Mapped[int] = mapped_column(Integer)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")

    fast_path_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deep_analysis_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    containment: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class ActionReceiptModel(Base):
    __tablename__ = "action_receipts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    inspection_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    intent_hash: Mapped[str] = mapped_column(String(64))
    tool_name: Mapped[str] = mapped_column(String(128))
    arguments_hash: Mapped[str] = mapped_column(String(64))
    resource: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    capability: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    decision: Mapped[str] = mapped_column(String(16))
    nonce: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(128))

    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    event_type: Mapped[str] = mapped_column(String(64), index=True)
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    session: Mapped[SessionModel] = relationship(back_populates="audit_events")


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    user_intent: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str] = mapped_column(String(128))
    tool_arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    risk_level: Mapped[str] = mapped_column(String(16))
    risk_score: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(16))
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    containment: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    session: Mapped[SessionModel] = relationship(back_populates="incidents")