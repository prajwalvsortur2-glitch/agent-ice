"""Structured security event shapes.

Events are dicts with a fixed key set. `emit_security_event` writes them
through the JSON logger at INFO level and (optionally) through the OTel
shim. This keeps a single emission path for all security-relevant activity.
"""
from __future__ import annotations

from typing import Any

from app.telemetry.logger import get_logger
from app.telemetry.otel import record_event

logger = get_logger("agent_ice.events")


_SECURITY_EVENT_TYPES = frozenset(
    {
        "session_created",
        "inspect",
        "inspect_rejected",
        "decision",
        "execution",
        "execution_denied",
        "approval",
        "rejection",
        "restriction",
        "incident",
        "policy_reloaded",
        "llm_unavailable",
        "llm_malformed",
        "fail_closed",
    }
)


def emit_security_event(
    *,
    event_type: str,
    session_id: str,
    payload: dict[str, Any],
    severity: str = "INFO",
) -> None:
    """Emit a structured security event.

    `event_type` should be one of `_SECURITY_EVENT_TYPES`. Unknown types are
    still emitted but flagged so they can be detected in review.
    """
    if event_type not in _SECURITY_EVENT_TYPES:
        logger.warning(
            "unknown security event type",
            extra={"event_type": event_type, "session_id": session_id},
        )

    log_method = logger.info
    if severity == "WARNING":
        log_method = logger.warning
    elif severity == "ERROR":
        log_method = logger.error
    elif severity == "CRITICAL":
        log_method = logger.critical

    log_method(
        f"security_event:{event_type}",
        extra={
            "event_type": event_type,
            "session_id": session_id,
            "severity": severity,
            "payload": payload,
        },
    )

    # Feed the OTel shim (no-op unless an exporter is installed).
    record_event(event_type=event_type, session_id=session_id, attributes=payload)