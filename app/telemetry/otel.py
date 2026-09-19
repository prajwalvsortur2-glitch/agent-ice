"""Minimal OpenTelemetry-compatible event sink.

This is deliberately thin: it accepts events and stores them on an
in-memory ring buffer that a real exporter could drain. It does NOT claim
OpenTelemetry spec compliance — it is a shim that a deployment can wire to
a real `opentelemetry-sdk` span/event exporter.

Usage:
    from app.telemetry.otel import record_event, install_exporter

    install_exporter(my_callable)  # callable(event_type, session_id, attributes)
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any, Callable

logger = logging.getLogger("agent_ice.otel")

EventExporter = Callable[[str, str, dict[str, Any]], None]

_lock = threading.Lock()
_buffer: deque[dict[str, Any]] = deque(maxlen=1000)
_exporter: EventExporter | None = None


def install_exporter(exporter: EventExporter) -> None:
    """Install a callable that will receive every recorded event."""
    global _exporter
    with _lock:
        _exporter = exporter
    logger.info("custom telemetry exporter installed")


def record_event(*, event_type: str, session_id: str, attributes: dict[str, Any]) -> None:
    """Record a single event. Never raises."""
    record = {
        "event_type": event_type,
        "session_id": session_id,
        "attributes": attributes,
    }
    with _lock:
        _buffer.append(record)
        exporter = _exporter

    if exporter is None:
        return
    try:
        exporter(event_type, session_id, attributes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("custom telemetry exporter raised: %s", exc)


def drain() -> list[dict[str, Any]]:
    """Remove and return all buffered events. Used by tests and debug tools."""
    with _lock:
        items = list(_buffer)
        _buffer.clear()
    return items


def peek(limit: int = 100) -> list[dict[str, Any]]:
    """Return up to `limit` buffered events without removing them."""
    with _lock:
        return list(_buffer)[-limit:]