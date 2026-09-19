"""High-level Qwen analyzer for Agent ICE drift analysis.

The analyzer:
  1. Builds the drift prompt.
  2. Calls the local Ollama client.
  3. Parses the JSON output safely.
  4. Returns a `DriftAssessment` — or None on any failure.

The caller (drift_engine) treats a None result as an inference failure and
applies fail-closed behavior for high-risk requests.
"""
from __future__ import annotations

import logging

from app.config import Settings
from app.ice.decision import Decision
from app.llm.ollama_client import OllamaClient, OllamaError
from app.llm.prompts import SYSTEM_PROMPT, build_drift_prompt
from app.llm.structured_output import safe_parse_json, validate_drift_payload
from app.models import DriftAssessment, IntentAnchor, PolicyFinding, ToolCall

logger = logging.getLogger(__name__)


class QwenAnalyzer:
    def __init__(
        self,
        settings: Settings,
        client: OllamaClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = client or OllamaClient(settings)

    # ------------------------------------------------------------------
    def analyze_drift(
        self,
        *,
        intent: IntentAnchor,
        tool_call: ToolCall,
        resource: str | None,
        capability: str | None,
        policy_findings: list[PolicyFinding] | None = None,
    ) -> DriftAssessment | None:
        """Return drift analysis from Qwen, or None on any failure."""
        prompt = build_drift_prompt(
            intent=intent,
            tool_call=tool_call,
            resource=resource,
            capability=capability,
            policy_findings=[f.model_dump(mode="json") for f in (policy_findings or [])],
        )

        try:
            raw = self._client.generate(prompt=prompt, system=SYSTEM_PROMPT, temperature=0.0)
        except OllamaError as exc:
            logger.warning("Qwen drift analysis unavailable: %s", exc)
            return None

        payload = safe_parse_json(raw)
        if payload is None:
            logger.warning("Qwen drift analysis produced unparsable output")
            return DriftAssessment(
                alignment="LOW",
                confidence=0.0,
                risk_delta=0,
                recommended_action=None,
                reasons=["LLM_MALFORMED: model output could not be parsed"],
                source="qwen",
                raw_model_output=raw[:1000],
            )

        ok, errors = validate_drift_payload(payload)
        if not ok:
            logger.warning("Qwen drift analysis schema errors: %s", errors)
            return DriftAssessment(
                alignment="LOW",
                confidence=0.0,
                risk_delta=0,
                recommended_action=None,
                reasons=[f"LLM_MALFORMED: {e}" for e in errors],
                source="qwen",
                raw_model_output=raw[:1000],
            )

        action_value = payload.get("recommended_action")
        try:
            action = Decision(action_value) if action_value else None
        except ValueError:
            action = None

        return DriftAssessment(
            alignment=str(payload["alignment"]),
            confidence=float(payload["confidence"]),
            risk_delta=int(payload["risk_delta"]),
            recommended_action=action,
            reasons=[str(r) for r in payload["reasons"]],
            source="qwen",
            raw_model_output=raw[:1000],
        )

    # ------------------------------------------------------------------
    def health(self) -> dict:
        return self._client.health()