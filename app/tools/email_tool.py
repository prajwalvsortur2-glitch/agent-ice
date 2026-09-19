"""Read-only email tool backed by controlled fixtures."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


_FIXTURE_PATH = Path("data/fixtures/emails.json")


class ReadEmailTool(BaseTool):
    name = "read_email"
    description = "Read a single email from the local inbox fixture by id."
    arguments_schema = {
        "required": ["id"],
        "properties": {
            "id": {"type": "string", "min_length": 1, "max_length": 128},
        },
        "additional_properties": False,
    }

    def __init__(self, fixture_path: Path | None = None) -> None:
        super().__init__()
        self._path = fixture_path or _FIXTURE_PATH
        self._emails: dict[str, dict[str, Any]] = self._load_fixtures()

    # ------------------------------------------------------------------
    def _load_fixtures(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("failed to load email fixtures: %s", exc)
            return {}

        if isinstance(raw, dict) and "emails" in raw:
            items = raw["emails"]
        elif isinstance(raw, list):
            items = raw
        else:
            logger.error("email fixtures have unexpected shape")
            return {}

        out: dict[str, dict[str, Any]] = {}
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                out[item["id"]] = item
        return out

    def reload(self) -> None:
        self._emails = self._load_fixtures()

    # ------------------------------------------------------------------
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        email_id = arguments.get("id")
        if not isinstance(email_id, str) or not email_id:
            return ToolResult(success=False, error="id must be a non-empty string")

        email = self._emails.get(email_id)
        if email is None:
            return ToolResult(success=False, error=f"email {email_id!r} not found")

        return ToolResult(
            success=True,
            data={
                "id": email.get("id"),
                "sender": email.get("sender"),
                "recipient": email.get("recipient"),
                "subject": email.get("subject"),
                "body": email.get("body"),
                "received_at": email.get("received_at"),
                # Content provenance is EXPLICIT so the agent must attach it
                # to any downstream tool call.
                "provenance": {
                    "source_id": email.get("id"),
                    "source_type": "email",
                    "trust_level": "UNTRUSTED",
                },
            },
        )

    def list_ids(self) -> list[str]:
        return sorted(self._emails.keys())