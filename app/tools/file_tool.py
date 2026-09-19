"""Read-only file tool with strict path allowlisting.

The tool refuses absolute paths, traversal, and any path that escapes the
configured allowlisted roots. Symlinks are resolved and re-checked.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.tools.base_tool import BaseTool, ToolResult

logger = logging.getLogger(__name__)


_ALLOWED_ROOTS = (Path("data/fixtures/files"), Path("data/fixtures/reports"))
_MAX_BYTES = 64 * 1024  # 64 KiB


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a text file from an allowlisted local directory."
    arguments_schema = {
        "required": ["path"],
        "properties": {
            "path": {"type": "string", "min_length": 1, "max_length": 512},
        },
        "additional_properties": False,
    }

    def __init__(self, allowed_roots: tuple[Path, ...] | None = None) -> None:
        super().__init__()
        self._roots = tuple(Path(r).resolve() for r in (allowed_roots or _ALLOWED_ROOTS))

    # ------------------------------------------------------------------
    def _resolve(self, raw_path: str) -> Path | None:
        if not isinstance(raw_path, str) or not raw_path:
            return None
        # Reject absolute paths and any traversal markers explicitly.
        if raw_path.startswith(("/", "\\")) or ".." in raw_path.replace("\\", "/").split("/"):
            return None
        if ":" in raw_path:  # e.g. C:\ or file:
            return None

        for root in self._roots:
            candidate = (root / raw_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            if candidate.is_file():
                return candidate
        return None

    # ------------------------------------------------------------------
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str):
            return ToolResult(success=False, error="path must be a string")

        resolved = self._resolve(raw_path)
        if resolved is None:
            return ToolResult(
                success=False,
                error="path is not within an allowlisted directory",
            )

        try:
            size = resolved.stat().st_size
        except OSError as exc:
            return ToolResult(success=False, error=f"stat failed: {exc}")

        if size > _MAX_BYTES:
            return ToolResult(success=False, error="file exceeds maximum readable size")

        try:
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(success=False, error=f"read failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "path": str(resolved.relative_to(resolved.anchor)) if resolved.is_absolute() else str(resolved),
                "size_bytes": size,
                "content": content,
                "provenance": {
                    "source_id": str(resolved),
                    "source_type": "internal_data",
                    "trust_level": "RESTRICTED",
                },
            },
        )