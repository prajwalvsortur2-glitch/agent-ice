"""Record mutation tool backed by fixtures.

`delete_record` is the canonical high-impact action used to demonstrate
REVIEW + step-up authorization. It NEVER mutates a real database; it marks
a record as `deleted=true` in a synthetic in-process store, seeded from the
customer fixtures.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


_FIXTURE_PATH = Path("data/fixtures/records.json")


class DeleteRecordTool(BaseTool):
    name = "delete_record"
    description = (
        "Mark a record as deleted in the synthetic store. High-impact, "
        "reversible only via the reset script."
    )
    arguments_schema = {
        "required": ["record_id"],
        "properties": {
            "record_id": {"type": "string", "min_length": 1, "max_length": 128},
            "reason": {"type": "string", "max_length": 500},
        },
        "additional_properties": False,
    }

    _lock = threading.Lock()
    _store: dict[str, dict[str, Any]] = {}
    _seeded = False
    _path = _FIXTURE_PATH

    def __init__(self, fixture_path: Path | None = None) -> None:
        super().__init__()
        type(self)._path = fixture_path or _FIXTURE_PATH
        self._ensure_seeded()

    # ------------------------------------------------------------------
    @classmethod
    def _ensure_seeded(cls) -> None:
        if cls._seeded:
            return
        with cls._lock:
            if cls._seeded:
                return
            cls._store.clear()
            try:
                raw = json.loads(cls._path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("failed to load record fixtures: %s", exc)
                raw = {"records": []}
            items = raw.get("records", raw) if isinstance(raw, dict) else raw
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and isinstance(item.get("id"), str):
                        cls._store[item["id"]] = dict(item, deleted=False, deleted_at=None)
            cls._seeded = True

    # ------------------------------------------------------------------
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        record_id = arguments.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            return ToolResult(success=False, error="record_id must be a non-empty string")

        with self._lock:
            row = self._store.get(record_id)
            if row is None:
                return ToolResult(success=False, error=f"record {record_id!r} not found")
            if row.get("deleted"):
                return ToolResult(success=True, data={"record_id": record_id, "already_deleted": True})
            row["deleted"] = True
            row["deleted_at"] = datetime.now(timezone.utc).isoformat()
            row["deleted_reason"] = arguments.get("reason", "")

        return ToolResult(
            success=True,
            data={
                "record_id": record_id,
                "deleted": True,
                "deleted_at": row["deleted_at"],
            },
        )

    # ------------------------------------------------------------------
    @classmethod
    def snapshot(cls) -> dict[str, dict[str, Any]]:
        with cls._lock:
            return {k: dict(v) for k, v in cls._store.items()}

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._store.clear()
            cls._seeded = False
        cls._ensure_seeded()