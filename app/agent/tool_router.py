"""The single execution boundary for protected tools.

The agent NEVER calls a tool directly. Every tool execution in the entire
application goes through `ToolRouter.execute(...)`, which enforces three
pre-conditions before touching the registry:

  1. A successful ICE inspection with decision == ALLOW (or an accepted
     RESTRICT containment) has produced a receipt.
  2. The receipt verifies (signature, binding, expiry).
  3. The receipt has not already been consumed.

If any check fails, the tool is not executed and the caller receives an
explicit denial.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.ice.controller import ICEController
from app.models import ToolCall
from app.storage.audit_repository import AuditRepository
from app.tools.base_tool import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionOutcome:
    success: bool
    executed_tool: str | None
    result: dict[str, Any] | None
    error: str | None
    audit_event_id: str | None
    latency_ms: float


class ToolRouter:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        ice_controller: ICEController,
        audit: AuditRepository,
    ) -> None:
        self._registry = registry
        self._ice = ice_controller
        self._audit = audit

    # ------------------------------------------------------------------
    def execute(
        self,
        *,
        session_id: str,
        receipt_token: str,
        tool_call: ToolCall,
    ) -> ExecutionOutcome:
        started = time.perf_counter()

        # 1. Receipt verification (single source of truth: the ICE controller).
        ok, reason_code, payload = self._ice.verify_receipt(
            session_id=session_id,
            receipt_token=receipt_token,
            tool_call=tool_call,
        )
        if not ok:
            latency_ms = (time.perf_counter() - started) * 1000.0
            try:
                event_id = self._audit.record_audit_event(
                    session_id=session_id,
                    event_type="execution_denied",
                    tool_name=tool_call.tool_name,
                    decision=None,
                    risk_level=None,
                    risk_score=None,
                    reason_codes=[reason_code or "RECEIPT_INVALID"],
                    latency_ms=latency_ms,
                    detail={"reason_code": reason_code or "RECEIPT_INVALID"},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("failed to record execution denial: %s", exc)
                event_id = None

            return ExecutionOutcome(
                success=False,
                executed_tool=None,
                result=None,
                error=f"execution denied: {reason_code}",
                audit_event_id=event_id,
                latency_ms=latency_ms,
            )

        # 2. Look up the tool. The registry is the ONLY place tools exist.
        tool = self._registry.get(tool_call.tool_name)
        if tool is None:
            latency_ms = (time.perf_counter() - started) * 1000.0
            event_id = self._audit.record_audit_event(
                session_id=session_id,
                event_type="execution_denied",
                tool_name=tool_call.tool_name,
                reason_codes=["UNKNOWN_TOOL"],
                latency_ms=latency_ms,
                detail={"reason_code": "UNKNOWN_TOOL"},
            )
            return ExecutionOutcome(
                success=False,
                executed_tool=None,
                result=None,
                error=f"unknown tool {tool_call.tool_name!r}",
                audit_event_id=event_id,
                latency_ms=latency_ms,
            )

        # 3. Execute. Tools are defensive and never raise.
        result: ToolResult = tool.execute(tool_call.arguments)
        latency_ms = (time.perf_counter() - started) * 1000.0

        # 4. Audit the execution. Never include the raw result body in the
        #    audit row if the tool returned sensitive fields; the tools
        #    already redact PII at source, but we still cap the summary.
        try:
            event_id = self._audit.record_audit_event(
                session_id=session_id,
                event_type="execution",
                tool_name=tool_call.tool_name,
                reason_codes=["EXECUTED"] if result.success else ["TOOL_ERROR"],
                latency_ms=latency_ms,
                detail={
                    "success": result.success,
                    "arguments_hash_present": bool(payload and payload.get("arguments_hash")),
                    "error": result.error,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to record execution event: %s", exc)
            event_id = None

        return ExecutionOutcome(
            success=result.success,
            executed_tool=tool_call.tool_name,
            result=result.data if result.success else None,
            error=result.error,
            audit_event_id=event_id,
            latency_ms=latency_ms,
        )