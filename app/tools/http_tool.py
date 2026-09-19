"""Safe HTTP fetch demo tool.

The tool exists for the legacy compatibility surface and demo dashboard, but it
does not perform arbitrary outbound calls. It validates URLs and emits a stub
result so the registry and enforcement tests can assert that blocked requests do
not execute the real operation.
"""
from __future__ import annotations

from typing import Any

from app.security.validators import is_safe_url
from app.tools.base_tool import BaseTool, ToolResult


class HttpFetchTool(BaseTool):
    name = "http_fetch"
    description = "Fetch a URL from an allowlisted host. Demo-only, no real outbound fetches."
    arguments_schema = {
        "required": ["url"],
        "properties": {
            "url": {"type": "string", "min_length": 1, "max_length": 2048},
        },
        "additional_properties": False,
    }

    def _execute(self, arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url")
        if not isinstance(url, str) or not url:
            return ToolResult(success=False, error="url is required")
        ok, reason = is_safe_url(url, allowed_domains=["company.local", "internal.company.local"])
        if not ok:
            return ToolResult(success=False, error=f"unsafe url rejected: {reason}")
        return ToolResult(
            success=True,
            data={
                "url": url,
                "status": "ok",
                "body": "demo response body",
            },
        )