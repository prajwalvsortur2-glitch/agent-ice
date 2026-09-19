"""Capability engine — least-privilege tool authorization.

Capabilities are configured in `policies/permissions.yaml`. If the file is
missing, a conservative default set is used. Capability decisions are always
deterministic and are never delegated to the LLM.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.ice.decision import ReasonCode

logger = logging.getLogger(__name__)


# Tool → capability path. Every protected tool MUST have an entry here.
TOOL_CAPABILITY_MAP: dict[str, str] = {
    "read_email": "email.read",
    "read_file": "filesystem.read",
    "query_database": "database.read",
    "send_email": "email.send",
    "delete_record": "database.delete",
}


# Conservative defaults if no policy file is present.
_DEFAULT_CAPABILITIES: dict[str, bool] = {
    "email.read": True,
    "filesystem.read": True,
    "database.read": True,
    "email.send": False,
    "database.delete": False,
}


@dataclass(frozen=True)
class CapabilityResult:
    allowed: bool
    capability: str | None
    reason_code: str | None
    message: str

    @property
    def reason(self) -> str:
        return self.message


class CapabilityEngine:
    def __init__(self, settings: Settings | dict[str, bool] | None = None, policies_dir: str | None = None) -> None:
        if isinstance(settings, dict):
            self._settings = Settings()
            self._policies_dir = Path(policies_dir or self._settings.policies_dir)
            self._capabilities = dict(settings)
            return
        self._settings = settings or Settings()
        self._policies_dir = Path(policies_dir or self._settings.policies_dir)
        self._capabilities = self._load_capabilities()

    # ------------------------------------------------------------------
    def _load_capabilities(self) -> dict[str, bool]:
        path = self._policies_dir / "permissions.yaml"
        if not path.exists():
            logger.warning(
                "permissions.yaml not found at %s; using conservative defaults",
                path,
            )
            return dict(_DEFAULT_CAPABILITIES)

        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.error("failed to read permissions.yaml: %s", exc)
            return dict(_DEFAULT_CAPABILITIES)

        caps = raw.get("capabilities")
        if not isinstance(caps, dict):
            logger.error("permissions.yaml missing 'capabilities' mapping")
            return dict(_DEFAULT_CAPABILITIES)

        merged: dict[str, bool] = dict(_DEFAULT_CAPABILITIES)
        for key, value in caps.items():
            merged[str(key)] = bool(value)
        return merged

    def reload(self) -> None:
        """Reload capabilities from disk. Used by tests and admin actions."""
        self._capabilities = self._load_capabilities()

    def list_capabilities(self) -> dict[str, bool]:
        return dict(self._capabilities)

    # ------------------------------------------------------------------
    def capability_for_tool(self, tool_name: str) -> str | None:
        return TOOL_CAPABILITY_MAP.get(tool_name)

    def check(self, tool_name: str, arguments: dict[str, Any] | None = None) -> CapabilityResult:
        """Return whether the agent is currently authorized for this tool."""
        capability = self.capability_for_tool(tool_name)
        if capability is None:
            return CapabilityResult(
                allowed=False,
                capability=None,
                reason_code=ReasonCode.CAPABILITY_NOT_FOUND,
                message=f"no capability mapping exists for tool {tool_name!r}",
            )

        if arguments is None:
            arguments = {}

        action = str((arguments or {}).get("operation", "")).upper()
        if tool_name == "query_database" and action in {"DELETE", "WRITE", "UPDATE"}:
            return CapabilityResult(
                allowed=False,
                capability=capability,
                reason_code=ReasonCode.CAPABILITY_DENIED,
                message="database write capability is not granted for this operation",
            )

        if tool_name == "read_file":
            path = str((arguments or {}).get("path", ""))
            if path and not any(path.startswith(prefix) for prefix in ("/reports", "reports", "data/fixtures/files")):
                return CapabilityResult(
                    allowed=False,
                    capability=capability,
                    reason_code=ReasonCode.CAPABILITY_DENIED,
                    message=f"filesystem read is restricted to allowlisted paths: {path!r}",
                )

        allowed = self._capabilities.get(capability, False)
        if not allowed:
            return CapabilityResult(
                allowed=False,
                capability=capability,
                reason_code=ReasonCode.CAPABILITY_DENIED,
                message=f"capability {capability!r} is not granted to this agent",
            )
        return CapabilityResult(
            allowed=True,
            capability=capability,
            reason_code=None,
            message=f"capability {capability!r} granted",
        )