"""Read-only database tool backed by fixtures.

The tool exposes a tiny, allowlisted query interface over a controlled
fixture. Arbitrary SQL is never executed. This is a deliberate design
choice for the demo: the pattern to reproduce in production is
"allowlisted parameterized queries, never raw SQL from an agent".
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


_FIXTURE_PATH = Path("data/fixtures/customers.json")
_ALLOWED_TABLES = {"customer_records"}
_MAX_ROWS = 50


class QueryDatabaseTool(BaseTool):
    name = "query_database"
    description = "Query customer_records using an allowlisted filter. Read-only."
    arguments_schema = {
        "required": ["table"],
        "properties": {
            "table": {"type": "string", "min_length": 1, "max_length": 64},
            "customer_id": {"type": "string", "min_length": 1, "max_length": 64},
            "limit": {"type": "integer", "min": 1, "max": _MAX_ROWS},
            # A raw `query` field is accepted by the schema but is IGNORED
            # for execution — presence of SQL keywords is a fast-path signal
            # that raises risk. The tool NEVER concatenates SQL.
            "query": {"type": "string", "max_length": 2000},
        },
        "additional_properties": False,
    }

    def __init__(self, fixture_path: Path | None = None) -> None:
        super().__init__()
        self._path = fixture_path or _FIXTURE_PATH
        self._records = self._load_fixtures()

    # ------------------------------------------------------------------
    def _load_fixtures(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("failed to load customer fixtures: %s", exc)
            return []
        if isinstance(raw, dict) and "customers" in raw:
            return [r for r in raw["customers"] if isinstance(r, dict)]
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        return []

    def reload(self) -> None:
        self._records = self._load_fixtures()

    # ------------------------------------------------------------------
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        table = arguments.get("table")
        if table not in _ALLOWED_TABLES:
            return ToolResult(
                success=False,
                error=f"table {table!r} is not in the allowlist",
            )

        limit_raw = arguments.get("limit", 10)
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            limit = 10
        limit = max(1, min(limit, _MAX_ROWS))

        customer_id = arguments.get("customer_id")
        rows = self._records
        if isinstance(customer_id, str) and customer_id:
            rows = [r for r in rows if r.get("id") == customer_id]

        rows = rows[:limit]

        # Return a redacted view: never expose full PII to the agent.
        redacted = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "email": _mask_email(r.get("email")),
                "segment": r.get("segment"),
            }
            for r in rows
        ]

        return ToolResult(
            success=True,
            data={
                "table": table,
                "row_count": len(redacted),
                "rows": redacted,
                "provenance": {
                    "source_id": f"database:{table}",
                    "source_type": "internal_data",
                    "trust_level": "RESTRICTED",
                },
            },
        )

    def count(self) -> int:
        return len(self._records)


def _mask_email(value: Any) -> str | None:
    if not isinstance(value, str) or "@" not in value:
        return None
    local, _, domain = value.partition("@")
    if not local:
        return value
    return f"{local[0]}***@{domain}"