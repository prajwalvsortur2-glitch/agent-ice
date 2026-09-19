"""Intent Anchor service.

Produces the immutable structured representation of the user's original goal
and provides a lightweight deterministic alignment check against a proposed
tool call.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field

from app.ice.decision import ReasonCode
from app.models import IntentAnchor as DomainIntentAnchor, ToolCall

logger = logging.getLogger(__name__)


# Simple keyword → tool hints used only as a bootstrap default.
_VERB_TO_OPERATION: dict[str, str] = {
    "summarize": "summarize",
    "read": "read",
    "list": "read",
    "find": "read",
    "search": "read",
    "lookup": "read",
    "extract": "extract",
    "draft": "draft",
    "compose": "draft",
    "prepare": "draft",
    "send": "send",
    "delete": "delete",
    "remove": "delete",
    "update": "write",
    "modify": "write",
    "write": "write",
    "create": "write",
    "query": "read",
    "generate": "extract",
}

_NOUN_TO_TOOL: dict[str, str] = {
    "email": "read_email",
    "emails": "read_email",
    "inbox": "read_email",
    "file": "read_file",
    "files": "read_file",
    "report": "read_file",
    "reports": "read_file",
    "database": "query_database",
    "record": "query_database",
    "records": "query_database",
    "customer": "query_database",
    "customers": "query_database",
}

# Tools whose use is always considered sensitive unless explicitly requested.
_HIGH_IMPACT_TOOLS: frozenset[str] = frozenset(
    {"send_email", "delete_record"}
)


@dataclass(frozen=True)
class IntentAnchor:
    """Compatibility wrapper for the older session-scoped intent contract."""

    session_id: str
    goal: str
    allowed_tools: list[str] = field(default_factory=list)
    allowed_operations: list[str] = field(default_factory=list)
    restricted_operations: list[str] = field(default_factory=list)
    intent_hash: str = ""
    created_at: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_tools", list(dict.fromkeys(self.allowed_tools)))
        object.__setattr__(self, "allowed_operations", list(dict.fromkeys(self.allowed_operations)))
        object.__setattr__(self, "restricted_operations", list(dict.fromkeys(self.restricted_operations)))

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "allowed_tools": list(self.allowed_tools),
            "allowed_operations": list(self.allowed_operations),
            "restricted_operations": list(self.restricted_operations),
            "intent_hash": self.intent_hash,
            "created_at": self.created_at,
        }


def create_intent_anchor(session_id: str, user_prompt: str) -> IntentAnchor:
    """Create a legacy session-scoped intent anchor used by the test suite."""
    service = IntentAnchorService()
    anchor, _ = service.bootstrap(user_prompt)
    return IntentAnchor(
        session_id=session_id,
        goal=anchor.goal,
        allowed_tools=list(anchor.allowed_tools),
        allowed_operations=list(anchor.allowed_operations),
        restricted_operations=list(anchor.restricted_operations),
        intent_hash=service.compute_hash(anchor),
        created_at=time.time(),
    )


class IntentAnchorService:
    """Builds and analyzes IntentAnchor objects."""

    # ------------------------------------------------------------------
    # Bootstrapping
    # ------------------------------------------------------------------
    def bootstrap(self, user_intent: str, agent_name: str = "qwen-agent") -> tuple[IntentAnchor, str]:
        """Return (IntentAnchor, intent_hash) for a new session."""
        if not isinstance(user_intent, str) or not user_intent.strip():
            raise ValueError("user_intent must be a non-empty string")

        goal = user_intent.strip()
        tokens = [t.lower() for t in re.split(r"[^A-Za-z0-9]+", goal) if t]

        allowed_tools: list[str] = []
        allowed_ops: list[str] = []
        restricted_ops: list[str] = []

        for tok in tokens:
            if tok in _NOUN_TO_TOOL:
                allowed_tools.append(_NOUN_TO_TOOL[tok])
            if tok in _VERB_TO_OPERATION:
                allowed_ops.append(_VERB_TO_OPERATION[tok])

        # Always implicit: reading the user's own content is safe if the noun
        # is present. Do not add high-impact tools.
        allowed_tools = [t for t in dict.fromkeys(allowed_tools) if t not in _HIGH_IMPACT_TOOLS]

        # Restricted operations always include destructive / outbound primitives.
        restricted_ops.extend(["send_email", "delete_email", "database_write", "delete_record"])
        restricted_ops = list(dict.fromkeys(restricted_ops))

        anchor = DomainIntentAnchor(
            goal=goal,
            allowed_tools=allowed_tools,
            allowed_operations=list(dict.fromkeys(allowed_ops)),
            restricted_operations=restricted_ops,
        )
        return anchor, self.compute_hash(anchor)

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------
    @staticmethod
    def compute_hash(anchor: DomainIntentAnchor | IntentAnchor) -> str:
        """Deterministic SHA-256 over the anchor's canonical JSON."""
        payload = json.dumps(
            anchor.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Alignment (deterministic only; deep analysis is drift_engine's job)
    # ------------------------------------------------------------------
    def deterministic_alignment(
        self,
        anchor: DomainIntentAnchor | IntentAnchor,
        tool_call: ToolCall,
    ) -> tuple[str, list[str], list[str]]:
        """Return (alignment, reasons, reason_codes).

        alignment ∈ {"LOW","MEDIUM","HIGH"} where HIGH means strong alignment.
        """
        reasons: list[str] = []
        codes: list[str] = []

        tool = tool_call.tool_name
        restricted = set(anchor.restricted_operations)
        allowed_tools = set(anchor.allowed_tools)

        # Explicit restriction always lowers alignment.
        if tool in restricted or tool in _HIGH_IMPACT_TOOLS:
            reasons.append(
                f"tool {tool!r} is in the restricted set for this intent"
            )
            codes.append(ReasonCode.INTENT_MISMATCH_HIGH)
            return "LOW", reasons, codes

        # Strong match: tool is directly in the anchor's tool allowlist.
        if allowed_tools and tool in allowed_tools:
            reasons.append(f"tool {tool!r} matches an allowed tool for the intent")
            return "HIGH", reasons, codes

        # Weak signal: tool family matches a verb in the goal.
        goal_lower = anchor.goal.lower()
        for verb, op in _VERB_TO_OPERATION.items():
            if not allowed_tools and verb in goal_lower and op in anchor.allowed_operations:
                if tool.startswith(("read_", "query_", "get_")) and op in {"read", "extract", "summarize"}:
                    reasons.append(
                        f"read-style tool {tool!r} is consistent with verb {verb!r}"
                    )
                    return "HIGH", reasons, codes

        # Legacy compatibility: a tool that is not in the intent allowlist is a
        # material mismatch. Returning LOW here ensures risk scoring and the
        # enforcement matrix treat it as non-trivial drift instead of silently
        # allowing the request.
        reasons.append(
            f"tool {tool!r} is not in the intent's allowed_tools list"
        )
        codes.append(ReasonCode.INTENT_MISMATCH_HIGH)
        return "LOW", reasons, codes