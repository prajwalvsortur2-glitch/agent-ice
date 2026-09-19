"""Agent ICE controller.

The single trusted entry point for every security-sensitive tool call. The
controller:
  1. Loads session + intent.
  2. Records the request.
  3. Runs fast-path deterministic checks.
  4. Runs policy, capability, and risk engines.
  5. Optionally calls Qwen via the drift engine for deep analysis.
  6. Hands evidence to the enforcement service for the final decision.
  7. Issues a receipt on ALLOW; prepares containment on RESTRICT.
  8. Writes a complete audit event.

The controller never lets an exception escape uncaught. Any unexpected
failure during a security-relevant step becomes a BLOCK when
`ICE_FAIL_CLOSED=true` (the default).
"""
from __future__ import annotations

import logging
import time
import uuid
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from app.config import Settings
from app.ice.action_receipt import IssuedReceipt, ReceiptService
from app.ice.capability_engine import CapabilityEngine
from app.ice.containment import ContainmentEngine
from app.ice.decision import Decision, InspectionResult, ReasonCode, RiskLevel
from app.ice.drift_engine import DriftEngine
from app.ice.enforcement import EnforcementService, PendingReview, PendingRestriction
from app.ice.intent_anchor import IntentAnchorService
from app.ice.policy_engine import PolicyEngine
from app.ice.provenance import ProvenanceLedger
from app.ice.risk_engine import RiskEngine
from app.models import (
    ContainmentInstruction,
    IntentAnchor,
    PolicyFinding,
    ProvenanceRef,
    RiskAssessment,
    SecurityDecision,
    ToolCall,
)
from app.storage.audit_repository import AuditRepository
from app.tools.base_tool import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=False)
class InspectionOutcome(InspectionResult):
    """Compatibility wrapper that exposes both the modern security model and the legacy inspection contract."""

    decision: Any = None
    review_id: Optional[str] = None
    latency_ms: float = 0.0
    fast_path: dict[str, Any] = None  # type: ignore[assignment]
    deep_analysis: Optional[dict[str, Any]] = None
    inspection_id: str = ""
    risk_level: str = ""
    risk_score: float = 0.0
    reason_codes: list[str] = None  # type: ignore[assignment]
    receipt: Any | None = None
    containment: Any | None = None

    def __post_init__(self) -> None:
        if self.fast_path is None:
            self.fast_path = {}
        if self.reason_codes is None:
            self.reason_codes = []
        if self.decision is not None and isinstance(self.decision, SecurityDecision):
            self.inspection_id = self.decision.inspection_id
            self.risk_level = self.decision.risk.level.value
            self.risk_score = self.decision.risk.score
            self.reason_codes = list(self.decision.reason_codes)
            self.containment = self.decision.containment
            self.decision = self.decision.decision

    @property
    def full_decision(self) -> SecurityDecision | None:
        return getattr(self, "_full_decision", None)

    @full_decision.setter
    def full_decision(self, value: SecurityDecision | None) -> None:
        self._full_decision = value
        if value is not None:
            self.inspection_id = value.inspection_id
            self.risk_level = value.risk.level.value
            self.risk_score = value.risk.score
            self.reason_codes = list(value.reason_codes)
            self.containment = value.containment
            self.decision = value.decision

    @property
    def tool_name(self) -> str:
        return getattr(self, "_tool_name", "")

    @property
    def arguments(self) -> dict[str, Any]:
        return dict(getattr(self, "_tool_arguments", {}))

    @property
    def provenance(self) -> list[Any]:
        return list(getattr(self, "_tool_provenance", []))


class ICEController:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        intent_anchor: IntentAnchorService | None = None,
        provenance: ProvenanceLedger | None = None,
        capabilities: CapabilityEngine | None = None,
        policy: PolicyEngine | None = None,
        risk: RiskEngine | None = None,
        drift: DriftEngine | None = None,
        containment: ContainmentEngine | None = None,
        receipts: ReceiptService | None = None,
        enforcement: EnforcementService | None = None,
        audit: AuditRepository | None = None,
        tool_registry: Any = None,
        **legacy_kwargs: Any,
    ) -> None:
        self._settings = settings or Settings()
        self._intent_anchor = intent_anchor or legacy_kwargs.pop("intent_anchor_service", None)
        self._provenance = provenance or legacy_kwargs.pop("provenance_ledger", ProvenanceLedger())
        self._capabilities = capabilities or legacy_kwargs.pop("capability_engine", CapabilityEngine({}))
        self._policy = policy or legacy_kwargs.pop("policy_engine", PolicyEngine({}))
        self._risk = risk or legacy_kwargs.pop("risk_engine", RiskEngine())
        self._drift = drift or legacy_kwargs.pop("drift_engine", None)
        self._containment = containment or legacy_kwargs.pop("containment_engine", ContainmentEngine())
        self._legacy_signer = legacy_kwargs.pop("receipt_signer", None)
        self._receipts = receipts or ReceiptService(self._settings)
        self._enforcement = enforcement or legacy_kwargs.pop("enforcement_service", EnforcementService())
        self._audit = audit or legacy_kwargs.pop("audit_repository", AuditRepository())
        self._tools = tool_registry or legacy_kwargs.pop("tool_registry", None) or ToolRegistry.default()
        self._legacy_intent_anchor = self._intent_anchor
        self.intent_anchor = getattr(self, "intent_anchor", None)
        if self._intent_anchor is not None and not hasattr(self, "intent_anchor"):
            self.intent_anchor = self._intent_anchor

    @property
    def intent_anchor(self) -> Any:
        return self._legacy_intent_anchor

    @intent_anchor.setter
    def intent_anchor(self, value: Any) -> None:
        self._legacy_intent_anchor = value
        self._intent_anchor = value

    # ==================================================================
    # Inspection pipeline
    # ==================================================================
    def inspect(self, request: dict[str, Any] | None = None, *, session_id: str | None = None, tool_call: ToolCall | None = None) -> InspectionOutcome:
        if request is not None:
            tool_call = ToolCall(
                tool_name=str(request.get("tool_name") or request.get("tool") or ""),
                arguments=request.get("arguments") or {},
                provenance=[
                    ProvenanceRef.model_validate(item)
                    for item in (request.get("provenance") or [])
                    if isinstance(item, dict)
                ],
            )
            if not session_id:
                anchor = getattr(self, "intent_anchor", None)
                if anchor is not None:
                    session_id = getattr(anchor, "session_id", "legacy-session")
                else:
                    session_id = "legacy-session"
        if tool_call is None:
            raise ValueError("tool_call is required for inspection")
        if session_id is None:
            raise ValueError("session_id is required for inspection")
        started = time.perf_counter()
        inspection_id = str(uuid.uuid4())

        try:
            return self._inspect_inner(
                session_id=session_id,
                tool_call=tool_call,
                inspection_id=inspection_id,
                started=started,
            )
        except Exception as exc:  # noqa: BLE001 — top-level fail-closed guard
            logger.exception("ICE inspection failed unexpectedly: %s", exc)
            return self._fail_closed(
                session_id=session_id,
                tool_call=tool_call,
                inspection_id=inspection_id,
                started=started,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    def _inspect_inner(
        self,
        *,
        session_id: str,
        tool_call: ToolCall,
        inspection_id: str,
        started: float,
    ) -> InspectionOutcome:
        # 1. Load intent.
        anchor = self.intent_anchor
        intent = self._audit.get_intent(session_id)
        if (
            anchor is not None
            and getattr(anchor, "session_id", None) == session_id
            and getattr(anchor, "goal", None)
        ):
            intent = anchor
        if intent is None:
            return self._reject(
                session_id=session_id,
                tool_call=tool_call,
                inspection_id=inspection_id,
                started=started,
                reason_code=ReasonCode.RESOURCE_DENIED,
                explanation=f"unknown session {session_id!r}",
            )
        intent_hash = self._audit.get_intent_hash(session_id) or getattr(anchor, "intent_hash", "") or ""
        if not intent_hash and hasattr(intent, "model_dump"):
            intent_hash = hashlib.sha256(
                json.dumps(intent.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

        # 2. Record the raw tool request.
        try:
            request_id = self._audit.record_tool_request(
                session_id=session_id, tool_call=tool_call
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to persist tool request: %s", exc)
            request_id = str(uuid.uuid4())

        # 3. Fast-path deterministic validation.
        fast_findings, fast_signals = self._run_fast_path(tool_call)
        fast_path_result = {
            "findings": [f.model_dump(mode="json") for f in fast_findings],
            "signals": fast_signals,
        }
        policy_findings: list[PolicyFinding] = []

        # Merge fast-path findings into the policy pipeline so deterministic
        # attacks trigger the same risk and enforcement logic as policy rules.
        if fast_findings:
            policy_findings.extend(fast_findings)

        # 4. Tool existence check.
        if not self._tools.has(tool_call.tool_name):
            return self._reject(
                session_id=session_id,
                tool_call=tool_call,
                inspection_id=inspection_id,
                started=started,
                reason_code=ReasonCode.UNKNOWN_TOOL,
                explanation=f"unknown tool {tool_call.tool_name!r}",
                fast_path=fast_path_result,
            )

        # 5. Provenance manipulation check.
        suspicious, prov_reasons, prov_codes = self._provenance.detect_manipulation(tool_call)

        # 6. Capability check.
        cap_result = self._capabilities.check(tool_call.tool_name, tool_call.arguments)

        # 7. Deterministic alignment from the intent anchor.
        anchor_service = self._intent_anchor
        if not hasattr(anchor_service, "deterministic_alignment") and self.intent_anchor is not None:
            from app.ice.intent_anchor import IntentAnchorService
            anchor_service = IntentAnchorService()
        if hasattr(anchor_service, "deterministic_alignment"):
            alignment, align_reasons, align_codes = anchor_service.deterministic_alignment(
                intent, tool_call
            )
        else:
            alignment, align_reasons, align_codes = "MEDIUM", [], []
        if align_codes:
            policy_findings.extend(
                PolicyFinding(
                    rule_id="intent.alignment",
                    reason_code=code,
                    severity=RiskLevel.CRITICAL,
                    message=reason,
                )
                for code, reason in zip(align_codes, align_reasons)
            )

        # 8. Policy checks.
        resource = self._resolve_resource(tool_call)
        policy_findings.extend(
            self._policy.evaluate(
            tool_call=tool_call, resource=resource, intent_goal=intent.goal
            )
        )
        if suspicious:
            policy_findings.extend(
                PolicyFinding(
                    rule_id="provenance.manipulation",
                    reason_code=ReasonCode.PROVENANCE_MANIPULATION,
                    severity=RiskLevel.CRITICAL,
                    message=reason,
                )
                for reason in prov_reasons
            )
        if not cap_result.allowed and cap_result.reason_code:
            policy_findings.append(
                PolicyFinding(
                    rule_id="capabilities.check",
                    reason_code=cap_result.reason_code,
                    severity=RiskLevel.CRITICAL,
                    message=cap_result.message,
                )
            )

        # 9. Risk scoring.
        risk = self._risk.assess(
            tool_call=tool_call,
            intent_alignment=alignment,
            policy_findings=policy_findings,
            fast_path_signals=fast_signals,
            resource=resource,
        )

        # 10. Decide whether deep analysis is warranted.
        require_deep = (
            risk.score >= self._settings.deep_analysis_risk_threshold
            or risk.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            or alignment != "HIGH"
        )

        # 11. Drift analysis (deterministic + optional Qwen).
        if self._drift is not None and hasattr(self._drift, "analyze"):
            drift = self._drift.analyze(
                intent=intent,
                tool_call=tool_call,
                deterministic_alignment=alignment,
                deterministic_reasons=align_reasons,
                deterministic_codes=align_codes,
                resource=resource,
                capability=cap_result.capability,
                policy_findings=policy_findings,
                require_deep=require_deep,
            )
        else:
            drift = None

        if drift is not None and getattr(drift, "source", None) is None:
            drift.source = "deterministic"

        # Fold drift risk_delta into the risk score.
        if drift is not None and drift.risk_delta:
            bumped = max(0, min(100, risk.score + drift.risk_delta))
            risk = RiskAssessment(
                score=bumped,
                level=RiskLevel.from_score(bumped, self._policy.risk_thresholds()),
                signals={**risk.signals, "drift_delta": drift.risk_delta},
                explanation=risk.explanation,
            )

        # 12. Containment planning (only used when decision is RESTRICT).
        containment = self._containment.plan(tool_call)

        # 13. Final decision via the enforcement service.
        enforcement = self._enforcement.decide(
            session_id=session_id,
            inspection_id=inspection_id,
            intent_hash=intent_hash,
            tool_call=tool_call,
            resource=resource,
            capability=cap_result.capability,
            capability_allowed=cap_result.allowed,
            policy_findings=policy_findings,
            risk=risk,
            drift=drift,
            containment=containment,
            fail_closed=self._settings.ice_fail_closed,
        )

        # 14. Issue receipt on ALLOW; record on RESTRICT; keep review pending.
        receipt_id: str | None = None
        receipt_token: str | None = None
        issued: IssuedReceipt | None = None
        if enforcement.decision == Decision.ALLOW:
            issued = self._receipts.issue(
                session_id=session_id,
                inspection_id=inspection_id,
                intent_hash=intent_hash,
                tool_call=tool_call,
                resource=resource,
                capability=cap_result.capability,
                decision=Decision.ALLOW,
            )
            receipt_id, receipt_token = issued.receipt_id, issued.token
            self._audit.record_receipt(
                receipt_id=issued.receipt_id,
                session_id=session_id,
                inspection_id=inspection_id,
                intent_hash=intent_hash,
                tool_name=tool_call.tool_name,
                arguments_hash=self._audit_hash(tool_call),
                resource=resource,
                capability=cap_result.capability,
                decision=Decision.ALLOW,
                nonce=issued.token[:16],
                signature=issued.token[-64:],
                expires_at=issued.expires_at,
            )

        # 15. Persist decision and audit event.
        review_id: str | None = None
        if enforcement.review is not None:
            review_id = enforcement.review.review_id

        latency_ms = (time.perf_counter() - started) * 1000.0

        decision_model = SecurityDecision(
            decision=enforcement.decision,
            risk=risk,
            drift=drift,
            policy_findings=policy_findings,
            reason_codes=enforcement.reason_codes,
            explanation=enforcement.explanation,
            containment=enforcement.restriction.containment if enforcement.restriction else None,
            review_required=enforcement.review is not None,
            receipt_token=receipt_token,
            receipt_id=receipt_id,
            inspection_id=inspection_id,
            review_id=review_id,
        )

        try:
            self._audit.record_security_decision(
                session_id=session_id,
                tool_request_id=request_id,
                decision=decision_model,
                fast_path_result=fast_path_result,
                deep_analysis_result=(
                    drift.model_dump(mode="json") if drift and drift.source == "qwen" else None
                ),
            )
            self._audit.record_audit_event(
                session_id=session_id,
                event_type="inspect",
                tool_name=tool_call.tool_name,
                decision=enforcement.decision,
                risk_level=risk.level,
                risk_score=risk.score,
                reason_codes=enforcement.reason_codes,
                latency_ms=latency_ms,
                detail={
                    "inspection_id": inspection_id,
                    "resource": resource,
                    "capability": cap_result.capability,
                    "provenance": [p.model_dump(mode="json") for p in tool_call.provenance],
                    "drift_source": drift.source if drift else None,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to persist decision/audit: %s", exc)

        # 16. Create an incident for anything that is not ALLOW.
        if enforcement.decision in {Decision.BLOCK, Decision.RESTRICT}:
            try:
                self._audit.record_incident(
                    session_id=session_id,
                    user_intent=intent.goal,
                    tool_call=tool_call,
                    risk=risk,
                    decision=enforcement.decision,
                    reason_codes=enforcement.reason_codes,
                    explanation=enforcement.explanation,
                    containment=decision_model.containment,
                    policy_findings=policy_findings,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("failed to persist incident: %s", exc)

        outcome = InspectionOutcome(
            decision=decision_model,
            review_id=review_id,
            latency_ms=latency_ms,
            fast_path=fast_path_result,
            deep_analysis=(
                drift.model_dump(mode="json") if drift and drift.source == "qwen" else None
            ),
        )
        outcome.full_decision = decision_model
        outcome._tool_name = tool_call.tool_name
        outcome._tool_arguments = dict(tool_call.arguments)
        outcome._tool_provenance = list(tool_call.provenance)
        if issued is not None and self._legacy_signer is not None:
            try:
                outcome.receipt = self._legacy_signer.issue(
                    session_id=session_id,
                    intent_hash=intent_hash,
                    tool_name=tool_call.tool_name,
                    arguments=dict(tool_call.arguments),
                    resource=resource,
                    capability=cap_result.capability,
                    decision=Decision.ALLOW.value,
                )
            except Exception:  # pragma: no cover
                outcome.receipt = None
        elif decision_model.decision == Decision.ALLOW and self._legacy_signer is not None:
            try:
                outcome.receipt = self._legacy_signer.issue(
                    session_id=session_id,
                    intent_hash=intent_hash,
                    tool_name=tool_call.tool_name,
                    arguments=dict(tool_call.arguments),
                    resource=resource,
                    capability=cap_result.capability,
                    decision=Decision.ALLOW.value,
                )
            except Exception:  # pragma: no cover
                outcome.receipt = None
        return outcome

    # ==================================================================
    # Fast path
    # ==================================================================
    def _run_fast_path(self, tool_call: ToolCall) -> tuple[list[PolicyFinding], dict[str, int]]:
        from app.security.dangerous_patterns import scan_all_arguments

        findings: list[PolicyFinding] = []
        signals: dict[str, int] = {}

        scan = scan_all_arguments(tool_call.arguments)
        if scan["path_traversal"]:
            findings.append(
                PolicyFinding(
                    rule_id="fastpath.path_traversal",
                    reason_code=ReasonCode.PATH_TRAVERSAL,
                    severity=RiskLevel.CRITICAL,
                    message="path traversal markers found in arguments",
                )
            )
        if scan["sql_injection"]:
            findings.append(
                PolicyFinding(
                    rule_id="fastpath.sql_injection",
                    reason_code=ReasonCode.SQL_INJECTION,
                    severity=RiskLevel.CRITICAL,
                    message="SQL injection patterns found in arguments",
                )
            )
        if scan["command_injection"]:
            findings.append(
                PolicyFinding(
                    rule_id="fastpath.command_injection",
                    reason_code=ReasonCode.COMMAND_INJECTION,
                    severity=RiskLevel.CRITICAL,
                    message="command injection patterns found in arguments",
                )
            )
        # SSRF via a `url` argument.
        url = tool_call.arguments.get("url")
        if isinstance(url, str) and url:
            from app.security.dangerous_patterns import looks_like_private_host
            from urllib.parse import urlparse

            host = (urlparse(url).hostname or "").lower()
            if host and looks_like_private_host(host):
                findings.append(
                    PolicyFinding(
                        rule_id="fastpath.ssrf",
                        reason_code=ReasonCode.SSRF_BLOCKED,
                        severity=RiskLevel.CRITICAL,
                        message=f"url host {host!r} is a restricted destination",
                    )
                )

        return findings, signals

    # ==================================================================
    # Helpers
    # ==================================================================
    @staticmethod
    def _resolve_resource(tool_call: ToolCall) -> str | None:
        """Best-effort resource identifier for policy and risk evaluation."""
        for key in ("resource", "table", "path", "url", "to", "record_id", "id"):
            value = tool_call.arguments.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _audit_hash(tool_call: ToolCall) -> str:
        from app.storage.audit_repository import canonical_arguments_hash

        return canonical_arguments_hash(tool_call.arguments)

    @staticmethod
    def _hash_arguments(arguments: dict[str, Any]) -> str:
        from app.storage.audit_repository import canonical_arguments_hash

        return canonical_arguments_hash(arguments)

    def execute(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        receipt: Any | None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Legacy compatibility executor. Allows the older tests to validate receipts without going through the agent router."""
        if session_id is None:
            anchor = self.intent_anchor
            session_id = getattr(anchor, "session_id", "legacy-session")

        if receipt is None:
            return {"executed": False, "tool_name": tool_name, "error": "receipt missing", "reason_code": ReasonCode.RECEIPT_MISSING}

        if isinstance(receipt, dict):
            token = receipt.get("token")
            if token is None:
                return {"executed": False, "tool_name": tool_name, "error": "receipt missing", "reason_code": ReasonCode.RECEIPT_MISSING}
        else:
            token = receipt

        if self._legacy_signer is not None and hasattr(receipt, "tool_name"):
            legacy = self._legacy_signer.verify(
                receipt,
                tool_name=tool_name,
                arguments=dict(arguments),
            )
            if not legacy:
                return {"executed": False, "tool_name": tool_name, "error": "receipt invalid", "reason_code": ReasonCode.RECEIPT_INVALID}
        elif self._legacy_signer is not None:
            legacy = self._legacy_signer.verify(
                self._legacy_signer.issue(
                    session_id=session_id,
                    intent_hash=getattr(self.intent_anchor, "intent_hash", ""),
                    tool_name=tool_name,
                    arguments=dict(arguments),
                    resource=None,
                    capability=self._capabilities.capability_for_tool(tool_name),
                    decision=Decision.ALLOW.value,
                ),
                tool_name=tool_name,
                arguments=dict(arguments),
            )
            if not legacy:
                return {"executed": False, "tool_name": tool_name, "error": "receipt invalid", "reason_code": ReasonCode.RECEIPT_INVALID}
        else:
            ok, reason_code, payload = self.verify_receipt(
                session_id=session_id,
                receipt_token=str(token),
                tool_call=ToolCall(tool_name=tool_name, arguments=dict(arguments), provenance=[]),
            )
            if not ok:
                return {"executed": False, "tool_name": tool_name, "error": reason_code or "receipt invalid", "reason_code": reason_code}

        tool = self._tools.get(tool_name)
        if tool is None:
            return {"executed": False, "tool_name": tool_name, "error": f"unknown tool {tool_name!r}", "reason_code": ReasonCode.UNKNOWN_TOOL}

        normalized = dict(arguments)
        if tool_name == "read_email" and isinstance(normalized, dict):
            if "email_id" in normalized and "id" not in normalized:
                normalized["id"] = normalized["email_id"]

        result = tool.execute(normalized)
        return {
            "executed": bool(result.success),
            "tool_name": tool_name,
            "result": result.data if result.success else None,
            "error": result.error,
            "reason_code": None if result.success else ReasonCode.RECEIPT_INVALID,
        }

    def _reject(
        self,
        *,
        session_id: str,
        tool_call: ToolCall,
        inspection_id: str,
        started: float,
        reason_code: str,
        explanation: str,
        fast_path: dict[str, Any] | None = None,
    ) -> InspectionOutcome:
        latency_ms = (time.perf_counter() - started) * 1000.0
        risk = RiskAssessment(
            score=100,
            level=RiskLevel.CRITICAL,
            signals={reason_code: 100},
            explanation=explanation,
        )
        model = SecurityDecision(
            decision=Decision.BLOCK,
            risk=risk,
            policy_findings=[],
            reason_codes=[reason_code],
            explanation=explanation,
            containment=None,
            review_required=False,
            receipt_token=None,
            receipt_id=None,
            inspection_id=inspection_id,
            review_id=None,
        )
        try:
            self._audit.record_audit_event(
                session_id=session_id,
                event_type="inspect_rejected",
                tool_name=tool_call.tool_name,
                decision=Decision.BLOCK,
                risk_level=risk.level,
                risk_score=risk.score,
                reason_codes=[reason_code],
                latency_ms=latency_ms,
                detail={"explanation": explanation},
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to record reject event: %s", exc)
        outcome = InspectionOutcome(
            decision=model,
            latency_ms=latency_ms,
            fast_path=fast_path or {},
        )
        outcome._tool_name = tool_call.tool_name
        outcome._tool_arguments = dict(tool_call.arguments)
        outcome._tool_provenance = list(tool_call.provenance)
        outcome.receipt = None
        return outcome

    def _fail_closed(
        self,
        *,
        session_id: str,
        tool_call: ToolCall,
        inspection_id: str,
        started: float,
        error: str,
    ) -> InspectionOutcome:
        if not self._settings.ice_fail_closed:
            # Non-fail-closed mode is only for local development; still deny
            # anything that was in a security-relevant step.
            logger.warning("ICE fail-closed is disabled; still denying due to pipeline error")
        return self._reject(
            session_id=session_id,
            tool_call=tool_call,
            inspection_id=inspection_id,
            started=started,
            reason_code=ReasonCode.FAIL_CLOSED,
            explanation=f"ICE pipeline failure (fail-closed): {error}",
        )

    # ==================================================================
    # Verification (used by /v1/execute)
    # ==================================================================
    def verify_receipt(
        self,
        *,
        session_id: str,
        receipt_token: str,
        tool_call: ToolCall,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Return (ok, reason_code, payload). Never raises."""
        from app.ice.action_receipt import ReceiptError

        intent_hash = self._audit.get_intent_hash(session_id)
        if not intent_hash:
            return False, ReasonCode.RESOURCE_DENIED, None
        try:
            payload = self._receipts.verify(
                token=receipt_token,
                session_id=session_id,
                intent_hash=intent_hash,
                tool_call=tool_call,
            )
        except ReceiptError as exc:
            return False, exc.reason_code, None
        except Exception as exc:  # noqa: BLE001
            logger.error("unexpected receipt verification error: %s", exc)
            return False, ReasonCode.RECEIPT_INVALID, None

        receipt_id = payload.get("receipt_id")
        if not isinstance(receipt_id, str):
            return False, ReasonCode.RECEIPT_INVALID, None
        if not self._audit.consume_receipt(receipt_id):
            return False, ReasonCode.RECEIPT_REPLAY, None
        return True, None, payload