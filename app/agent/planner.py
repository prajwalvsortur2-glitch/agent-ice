"""Deterministic planner used by the demo agent.

The planner is deliberately simple and reproducible: given a user intent and
a set of fixture inputs (emails, files, etc.), it produces a sequence of
proposed tool calls. The planner has no direct access to any tool; it only
emits proposals.

This module exists so the demo is deterministic and safe to run repeatedly.
The same design works with a real LLM planner — swap `plan` for a call to
the model and keep everything else.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.models import ProvenanceRef, ToolCall, TrustLevel

logger = logging.getLogger(__name__)


@dataclass
class Plan:
    """A sequence of proposed tool calls."""

    intent: str
    proposals: list[ToolCall] = field(default_factory=list)

    def append(self, call: ToolCall) -> None:
        self.proposals.append(call)


class Planner:
    """Deterministic proposal generator."""

    def plan_legitimate_email_summary(self, email_ids: list[str]) -> Plan:
        """User asked: 'Summarize my unread emails.' — read only."""
        plan = Plan(intent="summarize unread emails")
        for email_id in email_ids:
            plan.append(
                ToolCall(
                    tool_name="read_email",
                    arguments={"id": email_id},
                    provenance=[
                        ProvenanceRef(
                            source_id="user_prompt",
                            source_type="user_prompt",
                            trust_level=TrustLevel.TRUSTED,
                        )
                    ],
                )
            )
        return plan

    def plan_after_reading_email(
        self,
        *,
        email_id: str,
        email_body: str,
        forced_tool: str | None = None,
        forced_arguments: dict[str, Any] | None = None,
    ) -> ToolCall | None:
        """Given the content of a read email, propose the next action.

        This is where an LLM would normally decide what to do next. For the
        demo, the planner is deterministic: it detects an *obvious*
        injection marker in the email body and — if a `forced_tool` is
        provided — emits exactly the tool call the injection is trying to
        provoke. That lets the security test drive the attack path
        deterministically without an actual LLM being manipulated.
        """
        if not forced_tool:
            return None

        provenance = [
            ProvenanceRef(
                source_id=email_id,
                source_type="email",
                trust_level=TrustLevel.UNTRUSTED,
            )
        ]
        return ToolCall(
            tool_name=forced_tool,
            arguments=dict(forced_arguments or {}),
            provenance=provenance,
        )

    def plan_draft_email(self, to: str, subject: str, body: str) -> ToolCall:
        return ToolCall(
            tool_name="send_email",
            arguments={"to": to, "subject": subject, "body": body},
            provenance=[
                ProvenanceRef(
                    source_id="user_prompt",
                    source_type="user_prompt",
                    trust_level=TrustLevel.TRUSTED,
                )
            ],
        )

    def plan_delete_record(self, record_id: str, reason: str = "user requested") -> ToolCall:
        return ToolCall(
            tool_name="delete_record",
            arguments={"record_id": record_id, "reason": reason},
            provenance=[
                ProvenanceRef(
                    source_id="user_prompt",
                    source_type="user_prompt",
                    trust_level=TrustLevel.TRUSTED,
                )
            ],
        )