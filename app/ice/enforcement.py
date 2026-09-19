"""Enforcement — combines every signal into the final, authoritative decision.

This is the ONE place in the codebase that maps evidence to a Decision. No
other layer decides ALLOW / REVIEW / RESTRICT / BLOCK.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.ice.decision import Decision, ReasonCode, RiskLevel
from app.models import (
    ContainmentInstruction,
    DriftAssessment,
    PolicyFinding,
    RiskAssessment,
    ToolCall,
)

logger = logging.getLogger(__name__)


@dataclass
class PendingReview:
    """An outstanding REVIEW awaiting an explicit user approval."""

    review_id: str
    session_id: str
    inspection_id: str
    intent_hash: str
    tool_call: ToolCall
    resource: str | None
    capability: str | None
    risk: RiskAssessment
    explanation: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingRestriction:
    """An outstanding RESTRICT awaiting explicit user acknowledgment."""

    inspection_id: str
    session_id: str
    containment: ContainmentInstruction
    tool_call: ToolCall
    intent_hash: str
    resource: str | None
    capability: str | None


@dataclass(frozen=True)
class EnforcementResult:
    decision: Decision
    reason_codes: list[str]
    explanation: str
    review: PendingReview | None = None
    restriction: PendingRestriction | None = None


class EnforcementService:
    """Applies the decision matrix and stores pending REVIEW/RESTRICT state.

    The in-memory pending stores are appropriate for the single-process,
    single-user hackathon deployment. Multi-process deployments should
    replace these with a shared store; the interface stays the same.
    """

    def __init__(self) -> None:
        self._reviews: dict[str, PendingReview] = {}
        self._restrictions: dict[str, PendingRestriction] = {}

    # ------------------------------------------------------------------
    # Decision matrix
    # ------------------------------------------------------------------
    def decide(
        self,
        *,
        session_id: str,
        inspection_id: str,
        intent_hash: str,
        tool_call: ToolCall,
        resource: str | None,
        capability: str | None,
        capability_allowed: bool,
        policy_findings: list[PolicyFinding],
        risk: RiskAssessment,
        drift: DriftAssessment | None,
        containment: ContainmentInstruction | None,
        fail_closed: bool,
    ) -> EnforcementResult:
        reason_codes: list[str] = []
        explanations: list[str] = []

        # --- 1. Hard blocks (never allow under any model recommendation) ---
        critical_findings = [f for f in policy_findings if f.severity == RiskLevel.CRITICAL]
        if critical_findings:
            reason_codes.extend(f.reason_code for f in critical_findings)
            explanations.extend(f.message for f in critical_findings)
            return EnforcementResult(
                decision=Decision.BLOCK,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
            )

        if not capability_allowed:
            reason_codes.append(ReasonCode.CAPABILITY_DENIED)
            explanations.append("agent is not authorized for this capability")
            return EnforcementResult(
                decision=Decision.BLOCK,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
            )

        # --- 2. Critical risk is a hard block ---
        if risk.level == RiskLevel.CRITICAL:
            reason_codes.append(ReasonCode.POLICY_VIOLATION)
            explanations.append("risk score is CRITICAL")
            return EnforcementResult(
                decision=Decision.BLOCK,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
            )

        # --- 3. Low alignment + high risk → BLOCK ---
        if drift is not None and drift.alignment == "LOW" and risk.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            reason_codes.append(ReasonCode.INTENT_MISMATCH_HIGH)
            explanations.append("action shows low alignment with the original intent")
            return EnforcementResult(
                decision=Decision.BLOCK,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
            )

        # --- 4. LLM unavailable for high-risk → fail closed ---
        if fail_closed and drift is not None and drift.source == "deterministic" and risk.level == RiskLevel.HIGH:
            reason_codes.append(ReasonCode.FAIL_CLOSED)
            explanations.append("high-risk action could not be confirmed by deep analysis")
            return EnforcementResult(
                decision=Decision.BLOCK,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
            )

        # --- 5. High-risk with high impact → REVIEW ---
        high_findings = [f for f in policy_findings if f.severity == RiskLevel.HIGH]
        if risk.level == RiskLevel.HIGH:
            for f in high_findings:
                reason_codes.append(f.reason_code)
                explanations.append(f.message)
            reason_codes.append(ReasonCode.REVIEW_REQUIRED)
            explanations.append("high-impact action requires explicit user approval")

            review = PendingReview(
                review_id=str(uuid.uuid4()),
                session_id=session_id,
                inspection_id=inspection_id,
                intent_hash=intent_hash,
                tool_call=tool_call,
                resource=resource,
                capability=capability,
                risk=risk,
                explanation="; ".join(dict.fromkeys(explanations)),
            )
            self._reviews[review.review_id] = review
            return EnforcementResult(
                decision=Decision.REVIEW,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation=review.explanation,
                review=review,
            )

        # --- 6. Medium risk + downgrade available → RESTRICT ---
        if risk.level == RiskLevel.MEDIUM and containment is not None:
            reason_codes.append(ReasonCode.RESTRICTED_TO_SAFE_ACTION)
            explanations.append(containment.reason)

            restriction = PendingRestriction(
                inspection_id=inspection_id,
                session_id=session_id,
                containment=containment,
                tool_call=tool_call,
                intent_hash=intent_hash,
                resource=resource,
                capability=capability,
            )
            self._restrictions[inspection_id] = restriction
            return EnforcementResult(
                decision=Decision.RESTRICT,
                reason_codes=list(dict.fromkeys(reason_codes)),
                explanation="; ".join(dict.fromkeys(explanations)),
                restriction=restriction,
            )

        # --- 7. Otherwise ALLOW ---
        reason_codes.append(ReasonCode.ALLOWED)
        explanations.append("no policy violation detected and risk within tolerance")
        return EnforcementResult(
            decision=Decision.ALLOW,
            reason_codes=list(dict.fromkeys(reason_codes)),
            explanation="; ".join(dict.fromkeys(explanations)),
        )

    # ------------------------------------------------------------------
    # Review store
    # ------------------------------------------------------------------
    def get_review(self, review_id: str) -> PendingReview | None:
        return self._reviews.get(review_id)

    def pop_review(self, review_id: str) -> PendingReview | None:
        return self._reviews.pop(review_id, None)

    # ------------------------------------------------------------------
    # Restriction store
    # ------------------------------------------------------------------
    def get_restriction(self, inspection_id: str) -> PendingRestriction | None:
        return self._restrictions.get(inspection_id)

    def pop_restriction(self, inspection_id: str) -> PendingRestriction | None:
        return self._restrictions.pop(inspection_id, None)