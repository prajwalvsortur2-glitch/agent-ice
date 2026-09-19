"""Intent drift engine.

Combines deterministic alignment (from intent_anchor) with optional Qwen
contextual evidence. Qwen NEVER decides; it only contributes to `risk_delta`
and `reasons`.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.ice.decision import ReasonCode
from app.llm.qwen_analyzer import QwenAnalyzer
from app.models import DriftAssessment, IntentAnchor, PolicyFinding, ToolCall

logger = logging.getLogger(__name__)


class DriftEngine:
    def __init__(self, settings: Settings, qwen_analyzer: QwenAnalyzer) -> None:
        self._settings = settings
        self._qwen = qwen_analyzer

    # ------------------------------------------------------------------
    def analyze(
        self,
        *,
        intent: IntentAnchor,
        tool_call: ToolCall,
        deterministic_alignment: str,
        deterministic_reasons: list[str],
        deterministic_codes: list[str],
        resource: str | None,
        capability: str | None,
        policy_findings: list[PolicyFinding],
        require_deep: bool,
    ) -> DriftAssessment:
        """Return a DriftAssessment.

        If `require_deep` is False, only the deterministic result is returned.
        If `require_deep` is True and Qwen fails, a fail-closed placeholder
        is returned so the caller can decide.
        """
        base = DriftAssessment(
            alignment=deterministic_alignment,
            confidence=0.6 if deterministic_alignment == "MEDIUM" else 0.75,
            risk_delta=0,
            recommended_action=None,
            reasons=list(deterministic_reasons),
            source="deterministic",
        )

        if not require_deep:
            return base

        deep = self._qwen.analyze_drift(
            intent=intent,
            tool_call=tool_call,
            resource=resource,
            capability=capability,
            policy_findings=policy_findings,
        )

        if deep is None:
            # Fail closed: mark uncertainty and let enforcement escalate.
            return DriftAssessment(
                alignment=base.alignment,
                confidence=0.0,
                risk_delta=0,
                recommended_action=None,
                reasons=list(base.reasons) + [
                    "local model unavailable for deep analysis; treating as uncertain"
                ],
                source="deterministic",
            )

        # Combine deterministic + contextual signals conservatively: choose
        # the *lower* alignment of the two.
        combined_alignment = _lower_alignment(base.alignment, deep.alignment)

        # Confidence is capped at 0.95 to avoid implying certainty.
        confidence = min(0.95, max(base.confidence, deep.confidence))

        # Never let the model increase alignment to cancel a deterministic
        # mismatch. Only risk_delta from the model is used, and it is applied
        # additively — never to reduce below the deterministic signal.
        risk_delta = max(0, deep.risk_delta) if combined_alignment != "HIGH" else deep.risk_delta

        reasons = list(dict.fromkeys(base.reasons + deep.reasons))

        return DriftAssessment(
            alignment=combined_alignment,
            confidence=confidence,
            risk_delta=risk_delta,
            recommended_action=deep.recommended_action,
            reasons=reasons,
            source="qwen",
            raw_model_output=deep.raw_model_output,
        )


_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _lower_alignment(a: str, b: str) -> str:
    if a not in _ORDER:
        a = "LOW"
    if b not in _ORDER:
        b = "LOW"
    return a if _ORDER[a] <= _ORDER[b] else b