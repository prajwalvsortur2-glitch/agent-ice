"""Deterministic argument and resource validators.

These are the reusable primitives used by the fast-path gate and by mock
tools. They must be conservative: any ambiguity returns a deny.
"""
from __future__ import annotations

import ipaddress
import os
import re
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from app.security.dangerous_patterns import (
    looks_like_private_host,
    contains_path_traversal,
    scan_for_command_injection,
    scan_for_sql_injection,
)


class SecurityValidationError(ValueError):
    """Raised when a file path or URL fails the allowlist checks."""


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------
def resolve_within(base: str | os.PathLike[str], candidate: str) -> Path | None:
    """Return the resolved absolute path if it stays within `base`, else None."""
    try:
        base_path = Path(base).resolve()
        candidate_path = (base_path / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate_path.relative_to(base_path)
    except ValueError:
        return None
    return candidate_path


def is_safe_path(
    path: str,
    *,
    allowed_roots: Sequence[str | os.PathLike[str]],
) -> tuple[bool, str]:
    """Check `path` against a set of allowed root directories.

    Returns (ok, reason). Rejects absolute paths outside roots, traversal,
    symlink escape, and known sensitive markers.
    """
    if not isinstance(path, str) or not path:
        return False, "path is empty or not a string"
    if contains_path_traversal(path):
        return False, "path traversal markers detected"
    for root in allowed_roots:
        resolved = resolve_within(root, path)
        if resolved is not None:
            return True, "ok"
    return False, "path outside allowed roots"


# ---------------------------------------------------------------------------
# Network / SSRF
# ---------------------------------------------------------------------------
def _hostname_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    return (parsed.hostname or "").lower()


def is_safe_url(
    url: str,
    *,
    allowed_domains: Iterable[str],
    allow_private_hosts: bool = False,
    allowed_schemes: Sequence[str] = ("http", "https"),
) -> tuple[bool, str]:
    """Validate an external URL against SSRF and allowlist rules."""
    if not isinstance(url, str) or not url:
        return False, "url is empty"
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "url is unparsable"
    if parsed.scheme.lower() not in {s.lower() for s in allowed_schemes}:
        return False, f"scheme {parsed.scheme!r} not permitted"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "url has no hostname"

    # Reject literal private IPs and metadata hosts.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            if not allow_private_hosts:
                return False, f"private/reserved address {host} not permitted"
    except ValueError:
        # Not an IP literal.
        if looks_like_private_host(host) and not allow_private_hosts:
            return False, f"hostname {host!r} resolves to a restricted target"

    allowed = {d.lower() for d in allowed_domains}
    if allowed and not any(host == d or host.endswith("." + d) for d in allowed):
        return False, f"domain {host!r} not in allowlist"
    return True, "ok"


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------
def check_injection(text: str) -> dict[str, list[str]]:
    return {
        "sql": scan_for_sql_injection(text),
        "command": scan_for_command_injection(text),
    }


def detect_sql_injection(text: str) -> list[str]:
    return scan_for_sql_injection(text)


def detect_command_injection(text: str) -> list[str]:
    return scan_for_command_injection(text)


def validate_path(path: str, *, allowed_roots: Sequence[str | os.PathLike[str]]) -> None:
    ok, reason = is_safe_path(path, allowed_roots=allowed_roots)
    if not ok:
        raise SecurityValidationError(reason)


def validate_url(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    allow_private: bool = False,
) -> None:
    ok, reason = is_safe_url(
        url,
        allowed_domains=allowed_hosts,
        allow_private_hosts=allow_private,
    )
    if not ok:
        raise SecurityValidationError(reason)


# ---------------------------------------------------------------------------
# Email / recipient validation
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def is_valid_email(addr: str) -> bool:
    return bool(isinstance(addr, str) and _EMAIL_RE.match(addr.strip()))


def email_domain(addr: str) -> str:
    if not is_valid_email(addr):
        return ""
    return addr.rsplit("@", 1)[1].lower()


def is_external_email(addr: str, internal_domains: Iterable[str]) -> bool:
    dom = email_domain(addr)
    if not dom:
        return True
    internal = {d.lower() for d in internal_domains}
    return dom not in internal


# ---------------------------------------------------------------------------
# Argument schema validation
# ---------------------------------------------------------------------------
class SchemaError(ValueError):
    """Raised when a tool argument does not match its declared schema."""


def validate_schema(
    arguments: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate arguments against a tiny declarative schema.

    Schema shape (subset):
        {
          "required": ["a", "b"],
          "properties": {
             "a": {"type": "string", "max_length": 200},
             "b": {"type": "integer", "min": 0, "max": 100},
          },
          "additional_properties": False,
        }
    Supported types: string, integer, number, boolean, object, array.
    """
    errors: list[str] = []
    if not isinstance(arguments, dict):
        return False, ["arguments must be an object"]

    required = schema.get("required", [])
    for name in required:
        if name not in arguments:
            errors.append(f"missing required argument: {name}")

    props = schema.get("properties", {})
    if not schema.get("additional_properties", True):
        for name in arguments:
            if name not in props:
                errors.append(f"unexpected argument: {name}")

    for name, spec in props.items():
        if name not in arguments:
            continue
        value = arguments[name]
        t = spec.get("type")
        if t == "string" and not isinstance(value, str):
            errors.append(f"{name}: expected string")
            continue
        if t == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            errors.append(f"{name}: expected integer")
            continue
        if t == "number" and not isinstance(value, (int, float)):
            errors.append(f"{name}: expected number")
            continue
        if t == "boolean" and not isinstance(value, bool):
            errors.append(f"{name}: expected boolean")
            continue
        if t == "object" and not isinstance(value, dict):
            errors.append(f"{name}: expected object")
            continue
        if t == "array" and not isinstance(value, list):
            errors.append(f"{name}: expected array")
            continue

        if isinstance(value, str):
            if "max_length" in spec and len(value) > int(spec["max_length"]):
                errors.append(f"{name}: exceeds max_length {spec['max_length']}")
            if "min_length" in spec and len(value) < int(spec["min_length"]):
                errors.append(f"{name}: below min_length {spec['min_length']}")
            if "pattern" in spec:
                try:
                    if not re.match(spec["pattern"], value):
                        errors.append(f"{name}: does not match pattern")
                except re.error:
                    errors.append(f"{name}: invalid pattern spec")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "min" in spec and value < spec["min"]:
                errors.append(f"{name}: below min {spec['min']}")
            if "max" in spec and value > spec["max"]:
                errors.append(f"{name}: above max {spec['max']}")

    return (len(errors) == 0), errors