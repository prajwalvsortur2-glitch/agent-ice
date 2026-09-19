"""Safe JSON parsing for local-model output.

Qwen is instructed to emit a strict JSON object, but local models sometimes
wrap it in prose or code fences. This parser tries a strict pass first, then
a fence-aware fallback, then a brace-extraction fallback. It never raises:
a `None` return is treated as a model failure by the caller.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def safe_parse_json(text: str) -> dict[str, Any] | None:
    """Parse `text` into a dict, returning None if parsing is not possible."""
    if not isinstance(text, str) or not text.strip():
        return None

    # 1. Strict parse.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # 2. Fenced code block.
    fence = _FENCE_RE.search(text)
    if fence:
        try:
            parsed = json.loads(fence.group(1))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 3. First {...} span.
    brace = _JSON_OBJECT_RE.search(text)
    if brace:
        try:
            parsed = json.loads(brace.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    logger.warning("safe_parse_json failed on model output (len=%d)", len(text))
    return None


def validate_drift_payload(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate the drift-analysis JSON schema produced by Qwen.

    Required fields:
        alignment: "LOW" | "MEDIUM" | "HIGH"
        confidence: 0.0 .. 1.0
        risk_delta: -100 .. 100
        recommended_action: "ALLOW" | "REVIEW" | "RESTRICT" | "BLOCK"
        reasons: list[str]

    Returns (ok, errors). Missing/invalid fields produce errors.
    """
    errors: list[str] = []
    alignment = payload.get("alignment")
    if alignment not in {"LOW", "MEDIUM", "HIGH"}:
        errors.append("alignment must be LOW|MEDIUM|HIGH")

    conf = payload.get("confidence")
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        errors.append("confidence must be 0.0..1.0")

    delta = payload.get("risk_delta")
    if not isinstance(delta, (int, float)) or not -100 <= int(delta) <= 100:
        errors.append("risk_delta must be -100..100")

    action = payload.get("recommended_action")
    if action not in {"ALLOW", "REVIEW", "RESTRICT", "BLOCK"}:
        errors.append("recommended_action must be ALLOW|REVIEW|RESTRICT|BLOCK")

    reasons = payload.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(r, str) for r in reasons):
        errors.append("reasons must be a list of strings")

    return (len(errors) == 0), errors