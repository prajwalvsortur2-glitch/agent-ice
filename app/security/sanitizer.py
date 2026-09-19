"""Secret redaction and payload sanitization for logs/audit rows.

Logs and audit events must never persist secrets. This module is applied
automatically by the audit repository's `_redact_detail`.
"""
from __future__ import annotations

import re
from typing import Any


# Keys whose *values* must be redacted regardless of content.
SECRET_KEY_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "bearer",
        "session_secret",
        "signing_key",
        "receipt_secret",
        "private_key",
        "client_secret",
        "cookie",
        "set-cookie",
        "x-api-key",
    }
)

# Value patterns that look like secrets regardless of key name.
VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                       # OpenAI-style
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                      # GitHub PAT
    re.compile(r"AKIA[0-9A-Z]{16}"),                          # AWS key id
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),  # JWT
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
)

REDACTED = "[REDACTED]"


def _looks_like_secret_key(key: str) -> bool:
    return key.strip().lower() in SECRET_KEY_NAMES


def redact_string(value: str) -> str:
    """Return `value` with secret-looking substrings replaced."""
    out = value
    for pattern in VALUE_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out


def redact_secrets(obj: Any) -> Any:
    """Recursively redact secrets from any JSON-serializable structure.

    Dict keys matching `SECRET_KEY_NAMES` are redacted in place. String values
    that match known secret patterns are redacted. Lists/tuples/sets recurse.
    Non-serializable values are stringified.
    """
    if obj is None or isinstance(obj, (int, float, bool)):
        return obj
    if isinstance(obj, str):
        return redact_string(obj)
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key_str = str(k)
            if _looks_like_secret_key(key_str):
                out[key_str] = REDACTED
            else:
                out[key_str] = redact_secrets(v)
        return out
    if isinstance(obj, (list, tuple, set)):
        return [redact_secrets(v) for v in obj]
    return redact_string(str(obj))


def summarize_arguments(arguments: dict[str, Any], max_len: int = 240) -> dict[str, Any]:
    """Return a redacted, length-capped summary of tool arguments for logs."""
    redacted = redact_secrets(arguments)
    text = str(redacted)
    if len(text) <= max_len:
        return redacted if isinstance(redacted, dict) else {"value": redacted}
    return {"_truncated": True, "_preview": text[:max_len]}