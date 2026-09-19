"""Outbound email tool backed by fixtures.

This tool is the highest-impact protected action in the demo. It NEVER
sends anything externally — it appends to an in-memory outbox and returns
a synthetic message id. The demo reset script clears the outbox.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.security.validators import is_external_email, is_valid_email
from app.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


_INTERNAL_DOMAINS = ("company.local",)


class SendEmailTool(BaseTool):
    name = "send_email"
    description = "Send an email. In the demo, appends to a synthetic outbox."
    arguments_schema = {
        "required": ["to", "subject", "body"],
        "properties": {
            "to": {"type": "string", "min_length": 3, "max_length": 254},
            "subject": {"type": "string", "min_length": 1, "max_length": 200},
            "body": {"type": "string", "min_length": 1, "max_length": 20000},
            "attachments": {"type": "array"},
        },
        "additional_properties": False,
    }

    _lock = threading.Lock()
    _outbox: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        to = arguments.get("to")
        subject = arguments.get("subject")
        body = arguments.get("body")
        attachments = arguments.get("attachments") or []

        if not isinstance(to, str) or not is_valid_email(to):
            return ToolResult(success=False, error="invalid recipient address")
        if not isinstance(subject, str) or not subject.strip():
            return ToolResult(success=False, error="subject must be a non-empty string")
        if not isinstance(body, str) or not body.strip():
            return ToolResult(success=False, error="body must be a non-empty string")
        if not isinstance(attachments, list):
            return ToolResult(success=False, error="attachments must be a list")

        # Explicit external-destination check. ICE policy may already have
        # blocked this, but the tool must also defend itself.
        if is_external_email(to, _INTERNAL_DOMAINS):
            return ToolResult(
                success=False,
                error=f"external recipient {to!r} rejected by tool-level guard",
            )

        message = {
            "id": str(uuid.uuid4()),
            "to": to,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._outbox.append(message)

        return ToolResult(
            success=True,
            data={
                "message_id": message["id"],
                "to": to,
                "subject": subject,
                "attachment_count": len(attachments),
                "queued": True,
            },
        )

    # ------------------------------------------------------------------
    @classmethod
    def outbox(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return [dict(m) for m in cls._outbox]

    @classmethod
    def clear_outbox(cls) -> None:
        with cls._lock:
            cls._outbox.clear()