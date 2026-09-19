"""AgentService — orchestrates the demo agent's behavior.

The agent:
  * bootstraps a session with an intent anchor (via IntentBootstrap)
  * produces proposals (via Planner)
  * submits each proposal to Agent ICE for inspection
  * NEVER executes a tool directly — it hands the receipt to ToolRouter,
    which is the single execution boundary
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agent.intent_bootstrap import IntentBootstrap
from app.agent.planner import Planner
from app.agent.tool_router import ExecutionOutcome, ToolRouter
from app.config import Settings
from app.ice.controller import ICEController, InspectionOutcome
from app.ice.intent_anchor import IntentAnchorService
from app.llm.qwen_analyzer import QwenAnalyzer
from app.models import IntentAnchor, ToolCall
from app.tools.base_tool import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class ProposedAction:
    tool_call: ToolCall
    inspection: InspectionOutcome | None = None
    execution: ExecutionOutcome | None = None
    notes: list[str] = field(default_factory=list)


class AgentService:
    def __init__(
        self,
        *,
        settings: Settings,
        qwen_analyzer: QwenAnalyzer,
        intent_anchor: IntentAnchorService,
        ice_controller: ICEController,
        tool_registry: ToolRegistry,
    ) -> None:
        self._settings = settings
        self._qwen = qwen_analyzer
        self._intent = intent_anchor
        self._ice = ice_controller
        self._registry = tool_registry

        # The router is constructed here so the agent has exactly one way to
        # reach a tool: through the execution boundary.
        from app.storage.audit_repository import AuditRepository

        self._router = ToolRouter(
            registry=tool_registry,
            ice_controller=ice_controller,
            audit=AuditRepository(),
        )
        self._bootstrap = IntentBootstrap(intent_anchor)
        self._planner = Planner()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def build_intent(self, user_intent: str) -> tuple[IntentAnchor, str]:
        return self._bootstrap.build(user_intent)

    def propose(self, *, session_id: str, tool_call: ToolCall) -> ProposedAction:
        """Submit a proposed tool call to Agent ICE for inspection.

        Never executes anything. Returns the inspection outcome.
        """
        inspection = self._ice.inspect(session_id=session_id, tool_call=tool_call)
        return ProposedAction(tool_call=tool_call, inspection=inspection)

    def execute_authorized(
        self,
        *,
        session_id: str,
        receipt_token: str,
        tool_call: ToolCall,
    ) -> ExecutionOutcome:
        """Hand a *receipt-backed* tool call to the trusted executor.

        This is the ONLY way the agent ever reaches a tool. It cannot be
        reached without a valid, unconsumed receipt issued by ICE.
        """
        return self._router.execute(
            session_id=session_id,
            receipt_token=receipt_token,
            tool_call=tool_call,
        )

    # ------------------------------------------------------------------
    # Accessors used by demo scripts and the API layer.
    # ------------------------------------------------------------------
    @property
    def planner(self) -> Planner:
        return self._planner

    @property
    def router(self) -> ToolRouter:
        return self._router

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def tool_names(self) -> list[str]:
        return self._registry.names()

    def reset_tool_counters(self) -> None:
        self._registry.reset_counters()

    # ------------------------------------------------------------------
    # Used by tests: prove a tool was NOT executed.
    # ------------------------------------------------------------------
    def tool_execution_count(self, tool_name: str) -> int:
        tool = self._registry.get(tool_name)
        return tool.execution_count if tool is not None else -1

    def debug_snapshot(self) -> dict[str, Any]:
        return {
            "tools": self._registry.names(),
            "counts": {t.name: t.execution_count for t in self._registry.all_tools()},
        }