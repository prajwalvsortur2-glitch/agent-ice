"""Adaptive containment.

For RESTRICT decisions, the trusted executor must perform the downgrade.
This engine only computes the instruction; the executor enforces it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.models import ContainmentInstruction, ToolCall

logger = logging.getLogger(__name__)


# Downgrade table. Value is (replacement_tool, argument_transform).
# A transform is a callable taking the original arguments dict and returning
# a new dict. It must never simply re-emit the original arguments verbatim.
def _strip_attachments(args: dict[str, Any]) -> dict[str, Any]:
    out = dict(args)
    out.pop("attachments", None)
    out.pop("cc", None)
    out.pop("bcc", None)
    return out


def _read_only_arguments(args: dict[str, Any]) -> dict[str, Any]:
    """Keep only allow-listed read arguments; drop anything else."""
    allowed = {"id", "query", "table", "limit", "select"}
    return {k: v for k, v in args.items() if k in allowed}


DOWNGRADES: dict[str, tuple[str, Any]] = {
    "send_email": ("create_draft_email", _strip_attachments),
    "delete_record": ("get_record", _read_only_arguments),
    "query_database_write": ("query_database", _read_only_arguments),
    "write_database": ("read_database", _read_only_arguments),
    "external_http_post": ("local_preview_http", _read_only_arguments),
}


@dataclass(frozen=True)
class RestrictedAction:
    original_tool: str
    original_arguments: dict[str, Any]
    restricted_tool: str
    restricted_arguments: dict[str, Any]
    reason: str


class ContainmentEngine:
    def __init__(self, rules: dict[str, dict[str, Any]] | None = None) -> None:
        self._rules = self._normalize_rules(rules or DOWNGRADES)

    @staticmethod
    def _normalize_rules(rules: dict[str, Any]) -> dict[str, tuple[str, Any]]:
        normalized: dict[str, tuple[str, Any]] = {}
        for tool_name, rule in rules.items():
            if isinstance(rule, tuple) and len(rule) == 2:
                normalized[tool_name] = rule
                continue
            if isinstance(rule, dict):
                replacement = rule.get("to") or rule.get("replacement_tool")
                if replacement is None:
                    continue
                transform = rule.get("transform")
                if callable(transform):
                    normalized[tool_name] = (str(replacement), transform)
                else:
                    normalized[tool_name] = (str(replacement), lambda args, _rule=rule: _filter_restricted_args(args, _rule))
                continue
            raise TypeError(f"invalid containment rule for {tool_name!r}: {rule!r}")
        return normalized

    def can_restrict(self, tool_name: str) -> bool:
        return tool_name in self._rules

    def restrict(self, tool_name: str, arguments: dict[str, Any]) -> RestrictedAction:
        rule = self._rules.get(tool_name)
        if rule is None:
            raise ValueError(f"tool {tool_name!r} has no containment rule")
        replacement_tool, transform = rule
        replacement_args = transform(dict(arguments)) if callable(transform) else dict(arguments)
        return RestrictedAction(
            original_tool=tool_name,
            original_arguments=dict(arguments),
            restricted_tool=replacement_tool,
            restricted_arguments=replacement_args,
            reason=f"downgrade {tool_name!r} to {replacement_tool!r}",
        )


def _filter_restricted_args(args: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    filtered = dict(args)
    for key in ("attachments", "cc", "bcc", "body", "content", "payload", "sent"):
        if key in filtered and "keep" not in rule:
            filtered.pop(key, None)
    return filtered


class ContainmentEngine:
    def __init__(self, rules: dict[str, dict[str, Any]] | None = None) -> None:
        self._rules = self._normalize_rules(rules or DOWNGRADES)

    @staticmethod
    def _normalize_rules(rules: dict[str, Any]) -> dict[str, tuple[str, Any]]:
        normalized: dict[str, tuple[str, Any]] = {}
        for tool_name, rule in rules.items():
            if isinstance(rule, tuple) and len(rule) == 2:
                normalized[tool_name] = rule
                continue
            if isinstance(rule, dict):
                replacement = rule.get("to") or rule.get("replacement_tool")
                if replacement is None:
                    continue
                transform = rule.get("transform")
                if callable(transform):
                    normalized[tool_name] = (str(replacement), transform)
                else:
                    normalized[tool_name] = (str(replacement), lambda args, _rule=rule: _filter_restricted_args(args, _rule))
                continue
            raise TypeError(f"invalid containment rule for {tool_name!r}: {rule!r}")
        return normalized

    def can_restrict(self, tool_name: str) -> bool:
        return tool_name in self._rules

    def restrict(self, tool_name: str, arguments: dict[str, Any]) -> RestrictedAction:
        rule = self._rules.get(tool_name)
        if rule is None:
            raise ValueError(f"tool {tool_name!r} has no containment rule")
        replacement_tool, transform = rule
        replacement_args = transform(dict(arguments)) if callable(transform) else dict(arguments)
        return RestrictedAction(
            original_tool=tool_name,
            original_arguments=dict(arguments),
            restricted_tool=replacement_tool,
            restricted_arguments=replacement_args,
            reason=f"downgrade {tool_name!r} to {replacement_tool!r}",
        )

    def plan(self, tool_call: ToolCall) -> ContainmentInstruction | None:
        """Return a containment instruction if a safe downgrade exists."""
        entry = self._rules.get(tool_call.tool_name)
        if entry is None:
            return None
        replacement_tool, transform = entry
        try:
            replacement_args = transform(dict(tool_call.arguments))
        except Exception as exc:  # noqa: BLE001
            logger.warning("containment argument transform failed: %s", exc)
            replacement_args = {}
        return ContainmentInstruction(
            original_tool=tool_call.tool_name,
            replacement_tool=replacement_tool,
            replacement_arguments=replacement_args,
            reason=(
                f"tool {tool_call.tool_name!r} restricted to safer operation "
                f"{replacement_tool!r}"
            ),
        )

    def has_downgrade(self, tool_name: str) -> bool:
        return tool_name in self._rules