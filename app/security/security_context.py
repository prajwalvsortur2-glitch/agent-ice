"""A small immutable bag of context passed between ICE engines.

Keeping the context explicit prevents engines from reaching into globals and
makes unit testing trivial.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import IntentAnchor, ToolCall


@dataclass(frozen=True)
class SecurityContext:
    """Everything the ICE engines need about one proposed tool call."""

    session_id: str
    intent: IntentAnchor
    intent_hash: str
    tool_call: ToolCall
    agent_name: str = "qwen-agent"
    # Values populated as the pipeline runs.
    resolved_resource: str | None = None
    matched_capability: str | None = None
    extra: dict = field(default_factory=dict)