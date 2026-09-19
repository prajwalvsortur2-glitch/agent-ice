"""Unit tests for the Risk Engine.

Contract assumed from `app.ice.risk_engine`:

    @dataclass class RiskSignals:
        intent_mismatch: float = 0.0
        untrusted_provenance: float = 0.0
        resource_sensitivity: float = 0.0
        privilege_risk: float = 0.0
        destination_risk: float = 0.0
        reversibility_risk: float = 0.0
        policy_violation: float = 0.0
    @dataclass class RiskResult:
        score: float
        level: str               # LOW | MEDIUM | HIGH | CRITICAL
        components: dict[str, float]
    class RiskEngine:
        __init__(weights: dict, thresholds: dict)
        score(signals: RiskSignals) -> RiskResult
"""

from __future__ import annotations

import pytest

from app.ice.risk_engine import RiskEngine, RiskResult, RiskSignals


def test_zero_signals_is_low(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(RiskSignals())
    assert isinstance(result, RiskResult)
    assert result.score == 0
    assert result.level == "LOW"


def test_moderate_signals_is_medium(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(RiskSignals(intent_mismatch=0.5, untrusted_provenance=0.5))
    assert result.level in ("LOW", "MEDIUM")


def test_high_signals_high(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(
        RiskSignals(
            intent_mismatch=1.0,
            untrusted_provenance=1.0,
            resource_sensitivity=1.0,
            destination_risk=1.0,
        )
    )
    assert result.level in ("HIGH", "CRITICAL")


def test_max_signals_is_critical(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(
        RiskSignals(
            intent_mismatch=1.0,
            untrusted_provenance=1.0,
            resource_sensitivity=1.0,
            privilege_risk=1.0,
            destination_risk=1.0,
            reversibility_risk=1.0,
            policy_violation=1.0,
        )
    )
    assert result.level == "CRITICAL"


def test_components_are_explainable(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(RiskSignals(intent_mismatch=1.0, policy_violation=1.0))
    assert "intent_mismatch" in result.components
    assert "policy_violation" in result.components
    assert result.components["intent_mismatch"] > 0


def test_signals_are_clamped(risk_weights, risk_thresholds):
    engine = RiskEngine(risk_weights, risk_thresholds)
    result = engine.score(RiskSignals(intent_mismatch=99.0))
    assert result.score <= 100
    assert result.level == "CRITICAL"