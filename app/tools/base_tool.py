"""Base tool interface and registry.

Tools are invoked ONLY by the trusted executor, and ONLY after Agent ICE has
issued and the executor has verified a valid action receipt. Tools never
accept a call from the agent directly.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result returned by a tool execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class BaseTool(ABC):
    """Base class for all Agent ICE tools.

    Subclasses must declare `name`, `description`, `arguments_schema`, and
    implement `_execute`.
    """

    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    arguments_schema: ClassVar[dict[str, Any]] = {
        "required": [],
        "properties": {},
        "additional_properties": True,
    }

    def __init__(self) -> None:
        # Counter used by tests and the evaluation harness to prove a tool
        # was NOT executed when ICE blocked the call.
        self.execution_count: int = 0
        self.last_arguments: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Validate arguments and execute. Never raises."""
        self.execution_count += 1
        self.last_arguments = dict(arguments)

        try:
            result = self._execute(arguments)
        except Exception as exc:  # noqa: BLE001 — tools must never crash the executor
            logger.exception("tool %s raised during execution: %s", self.name, exc)
            return ToolResult(success=False, error=f"tool error: {exc}")

        if not isinstance(result, ToolResult):
            logger.error("tool %s returned an unexpected type", self.name)
            return ToolResult(success=False, error="tool returned an unexpected result type")
        return result

    # ------------------------------------------------------------------
    @abstractmethod
    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        """Implement the actual tool behavior. Must be defensive."""

    def reset_counter(self) -> None:
        """Reset the execution counter. Used by tests and the demo script."""
        self.execution_count = 0
        self.last_arguments = None

    def reset_execution_count(self) -> None:
        """Legacy compatibility alias used by older tests."""
        self.reset_counter()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{self.__class__.__name__} name={self.name!r} count={self.execution_count}>"


class ToolRegistry:
    """Registry of available tools, keyed by tool name."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("tool must declare a name")
        if tool.name in self._tools:
            logger.warning("overwriting existing tool %s", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def require(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def reset_counters(self) -> None:
        for tool in self._tools.values():
            tool.reset_counter()

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    @classmethod
    def default(cls) -> "ToolRegistry":
        from app.tools.communication_tool import SendEmailTool
        from app.tools.database_tool import QueryDatabaseTool
        from app.tools.email_tool import ReadEmailTool
        from app.tools.file_tool import ReadFileTool
        from app.tools.http_tool import HttpFetchTool
        from app.tools.record_tool import DeleteRecordTool

        registry = cls()
        registry.register(ReadEmailTool())
        registry.register(ReadFileTool())
        registry.register(QueryDatabaseTool())
        registry.register(SendEmailTool())
        registry.register(DeleteRecordTool())
        registry.register(HttpFetchTool())
        return registry

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools