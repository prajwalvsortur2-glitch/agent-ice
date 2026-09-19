"""Explainable risk engine.

Combines deterministic signals into a single 0..100 score, then maps to a
RiskLevel using configurable thresholds. The weights are configurable and
documented — they are not claimed to be scientifically universal.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.ice.decision import ReasonCode, RiskLevel
from app.models import PolicyFinding, ProvenanceRef, RiskAssessment, ToolCall, TrustLevel
from app.security.dangerous_patterns import (
    classify_operation_keywords,
    is_sensitive_resource,
)

logger = logging.getLogger(__name__)


# Default signal weights. Configurable via `policies/risk_thresholds.yaml`
# (`weights:` mapping). These are intentionally conservative.
DEFAULT_WEIGHTS: dict[str, int] = {
    "intent_mismatch_low": 15,     # MEDIUM alignment contribution
    "intent_mismatch_high": 35,    # LOW alignment contribution
    "untrusted_provenance": 25,
    "restricted_provenance": 5,
    "sensitive_resource": 15,
    "external_destination": 25,
    "high_impact_operation": 20,
    "destructive_operation": 30,
    "irreversible_operation": 20,
    "credential_access": 30,
    "policy_violation": 20,
    "path_traversal": 40,
    "sql_injection": 40,
    "command_injection": 40,
    "ssrf": 40,
}


@dataclass(frozen=True)
class RiskSignals:
    intent_mismatch: float = 0.0
    untrusted_provenance: float = 0.0
    resource_sensitivity: float = 0.0
    privilege_risk: float = 0.0
    destination_risk: float = 0.0
    reversibility_risk: float = 0.0
    policy_violation: float = 0.0


@dataclass(frozen=True)
class RiskResult:
    score: float
    level: str
    components: dict[str, float]


class RiskEngine:
    def __init__(self, settings: Settings | dict[str, int] | None = None, weights: dict[str, int] | None = None, thresholds: dict[str, int] | None = None) -> None:
        if isinstance(settings, dict) and weights is not None:
            self._settings = Settings()
            self._weights = dict(DEFAULT_WEIGHTS)
            self._weights.update(settings)
            self._thresholds = dict(thresholds or weights or {"low_max": 24, "medium_max": 49, "high_max": 79})
            return
        if isinstance(settings, dict):
            self._settings = Settings()
            self._weights = dict(DEFAULT_WEIGHTS)
            self._weights.update(settings)
            self._thresholds = dict(thresholds or {"low_max": 24, "medium_max": 49, "high_max": 79})
            return
        self._settings = settings or Settings()
        self._weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self._weights.update(weights)
        self._thresholds = dict(thresholds or {"low_max": 24, "medium_max": 49, "high_max": 79})

    def _legacy_score(self, signals: RiskSignals) -> RiskResult:
        def signal_value(raw: float, *, strong_weight: int, light_weight: int | None = None) -> float:
            value = float(raw)
            if value < 0.0:
                value = 0.0
            if value <= 1.0:
                weight = strong_weight if value >= 0.5 else (light_weight or strong_weight)
                return min(max(value * weight, 0.0), 100.0)
            return min(max(value, 0.0), 100.0)

        components = {
            "intent_mismatch": signal_value(
                signals.intent_mismatch,
                strong_weight=self._weights.get("intent_mismatch_high", 35),
                light_weight=self._weights.get("intent_mismatch_low", 15),
            ),
            "untrusted_provenance": signal_value(
                signals.untrusted_provenance,
                strong_weight=self._weights.get("untrusted_provenance", 25),
            ),
            "resource_sensitivity": signal_value(
                signals.resource_sensitivity,
                strong_weight=self._weights.get("sensitive_resource", 15),
            ),
            "privilege_risk": signal_value(
                signals.privilege_risk,
                strong_weight=self._weights.get("credential_access", 30),
            ),
            "destination_risk": signal_value(
                signals.destination_risk,
                strong_weight=self._weights.get("external_destination", 25),
            ),
            "reversibility_risk": signal_value(
                signals.reversibility_risk,
                strong_weight=self._weights.get("irreversible_operation", 20),
            ),
            "policy_violation": signal_value(
                signals.policy_violation,
                strong_weight=self._weights.get("policy_violation", 20),
            ),
        }
        score = min(100.0, sum(components.values()))
        level = RiskLevel.from_score(int(score), self._thresholds)
        return RiskResult(score=score, level=level.value, components=components)

    def score(self, signals: RiskSignals) -> RiskResult:
        return self._legacy_score(signals)

    def set_weights(self, weights: dict[str, int]) -> None:
        self._weights = {**DEFAULT_WEIGHTS, **weights}

    # ------------------------------------------------------------------
    def assess(
        self,
        *,
        tool_call: ToolCall,
        intent_alignment: str,
        policy_findings: list[PolicyFinding],
        fast_path_signals: dict[str, int] | None = None,
        resource: str | None = None,
    ) -> RiskAssessment:
        signals: dict[str, int] = {}
        reasons: list[str] = []

        # 1. Intent alignment
        if intent_alignment == "LOW":
            signals["intent_mismatch"] = self._weights["intent_mismatch_high"]
            reasons.append("action drifts significantly from the original intent")
        elif intent_alignment == "MEDIUM":
            signals["intent_mismatch"] = self._weights["intent_mismatch_low"]
            reasons.append("action partially drifts from the original intent")

        # 2. Provenance
        prov = _classify_provenance(tool_call.provenance)
        if prov["untrusted"]:
            signals["untrusted_provenance"] = self._weights["untrusted_provenance"]
            reasons.append("request is influenced by untrusted external content")
        if prov["restricted"]:
            signals["restricted_provenance"] = self._weights["restricted_provenance"]

        # 3. Resource sensitivity
        if resource and is_sensitive_resource(resource):
            signals["sensitive_resource"] = self._weights["sensitive_resource"]
            reasons.append(f"resource {resource!r} is sensitive")

        # 4. Operation classification
        op = classify_operation_keywords(tool_call.tool_name, str(tool_call.arguments))
        if op["destructive"]:
            signals["destructive_operation"] = self._weights["destructive_operation"]
            reasons.append("operation is classified as destructive")
        if op["high_impact"]:
            signals["high_impact_operation"] = self._weights["high_impact_operation"]
            reasons.append("operation is classified as high-impact")
        if op["irreversible"]:
            signals["irreversible_operation"] = self._weights["irreversible_operation"]
            reasons.append("operation is difficult to reverse")

        # 5. Policy findings
        for finding in policy_findings:
            key = _policy_to_signal_key(finding.reason_code)
            if key is not None:
                signals[key] = max(signals.get(key, 0), self._weights.get(key, finding.severity_weight()))
                reasons.append(finding.message)

        # 6. Fast-path signals (pre-computed by controller)
        if fast_path_signals:
            for key, value in fast_path_signals.items():
                signals[key] = max(signals.get(key, 0), int(value))

        score = min(100, sum(signals.values()))
        thresholds = _load_thresholds(self._settings)
        level = RiskLevel.from_score(score, thresholds)

        explanation = "; ".join(dict.fromkeys(reasons)) or "no material risk signals"
        return RiskAssessment(
            score=score,
            level=level,
            signals=signals,
            explanation=explanation,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_provenance(refs: list[ProvenanceRef]) -> dict[str, bool]:
    return {
        "untrusted": any(r.trust_level == TrustLevel.UNTRUSTED for r in refs),
        "restricted": any(r.trust_level == TrustLevel.RESTRICTED for r in refs),
        "trusted": any(r.trust_level == TrustLevel.TRUSTED for r in refs),
    }


def _policy_to_signal_key(reason_code: str) -> str | None:
    mapping = {
        ReasonCode.SENSITIVE_RESOURCE: "sensitive_resource",
        ReasonCode.EXTERNAL_DESTINATION_DENIED: "external_destination",
        ReasonCode.HIGH_IMPACT_ACTION: "high_impact_operation",
        ReasonCode.DESTRUCTIVE_OPERATION: "destructive_operation",
        ReasonCode.POLICY_VIOLATION: "policy_violation",
        ReasonCode.PATH_TRAVERSAL: "path_traversal",
        ReasonCode.SQL_INJECTION: "sql_injection",
        ReasonCode.COMMAND_INJECTION: "command_injection",
        ReasonCode.SSRF_BLOCKED: "ssrf",
    }
    return mapping.get(reason_code)


def _load_thresholds(settings: Settings) -> dict[str, int]:
    """Attempt to load thresholds from YAML; fall back to defaults."""
    from pathlib import Path
    import yaml

    path = Path(settings.policies_dir) / "risk_thresholds.yaml"
    if not path.exists():
        return {"low_max": 24, "medium_max": 49, "high_max": 79}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — defensively fall back
        return {"low_max": 24, "medium_max": 49, "high_max": 79}
    thresholds = (data.get("thresholds") if isinstance(data, dict) else None) or {}
    return {
        "low_max": int(thresholds.get("low_max", 24)),
        "medium_max": int(thresholds.get("medium_max", 49)),
        "high_max": int(thresholds.get("high_max", 79)),
    }


# Small helper used above.
def _severity_weight(level: RiskLevel) -> int:
    return {
        RiskLevel.LOW: 5,
        RiskLevel.MEDIUM: 10,
        RiskLevel.HIGH: 20,
        RiskLevel.CRITICAL: 30,
    }[level]


# Attach as a method for convenience.
RiskAssessment.__dict__  # noqa: B018 — keep linters from complaining about import only
PolicyFinding.severity_weight = lambda self: _severity_weight(self.severity)  # type: ignore[attr-defined]