"""Deterministic dangerous-pattern catalogue.

Used by the fast-path gate. Patterns are intentionally conservative: they
detect obvious injection and exfiltration shapes and are combined with
policy checks — they are not a substitute for policy.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Pattern


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------
SQL_INJECTION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bUNION\s+(?:ALL\s+)?SELECT\b", re.IGNORECASE),
    re.compile(r";\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\b", re.IGNORECASE),
    re.compile(r"\bOR\s+1\s*=\s*1\b", re.IGNORECASE),
    re.compile(r"\bOR\s+'1'\s*=\s*'1'(?=\s|$)", re.IGNORECASE),
    re.compile(r"--\s", re.IGNORECASE),
    re.compile(r"/\*.*?\*/", re.DOTALL),
    re.compile(r"\bxp_cmdshell\b", re.IGNORECASE),
    re.compile(r"\bLOAD_FILE\s*\(", re.IGNORECASE),
    re.compile(r"\bINTO\s+OUTFILE\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Command injection
# ---------------------------------------------------------------------------
COMMAND_INJECTION_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"[;&|`]\s*\w+"),
    re.compile(r"\$\([^)]*\)"),
    re.compile(r"`[^`]*`"),
    re.compile(r"\|\|\s*\w+"),
    re.compile(r"&&\s*\w+"),
    re.compile(r"\brm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r"\bcurl\s+[^|]*\|\s*(?:ba)?sh\b", re.IGNORECASE),
    re.compile(r"\bwget\s+[^|]*\|\s*(?:ba)?sh\b", re.IGNORECASE),
    re.compile(r"\bnc\s+-[a-z]*e\b", re.IGNORECASE),
)


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------
PATH_TRAVERSAL_MARKERS: tuple[str, ...] = (
    "../",
    "..\\",
    "%2e%2e",
    "%2e%2e%2f",
    "..%2f",
    "..%5c",
    "/etc/passwd",
    "/etc/shadow",
    "c:\\windows",
    "c:/windows",
)


# ---------------------------------------------------------------------------
# SSRF / metadata
# ---------------------------------------------------------------------------
PRIVATE_IP_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"^127\."),
    re.compile(r"^10\."),
    re.compile(r"^192\.168\."),
    re.compile(r"^172\.(?:1[6-9]|2\d|3[01])\."),
    re.compile(r"^169\.254\."),
    re.compile(r"^0\."),
    re.compile(r"^::1$"),
    re.compile(r"^fc00:", re.IGNORECASE),
    re.compile(r"^fe80:", re.IGNORECASE),
)

METADATA_HOSTS: frozenset[str] = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }
)


# ---------------------------------------------------------------------------
# Destructive / high-impact keywords
# ---------------------------------------------------------------------------
DESTRUCTIVE_KEYWORDS: frozenset[str] = frozenset(
    {
        "delete",
        "drop",
        "truncate",
        "destroy",
        "remove",
        "purge",
        "wipe",
        "erase",
        "unlink",
        "kill",
        "shutdown",
        "reboot",
        "format",
    }
)

HIGH_IMPACT_KEYWORDS: frozenset[str] = frozenset(
    {
        "send",
        "email",
        "transfer",
        "upload",
        "post",
        "publish",
        "payment",
        "charge",
        "wire",
        "grant",
        "revoke",
        "modify",
        "update",
        "write",
        "create",
        "approve",
    }
)

IRREVERSIBLE_KEYWORDS: frozenset[str] = frozenset(
    {
        "delete",
        "drop",
        "truncate",
        "send",
        "transfer",
        "publish",
        "wire",
        "payment",
    }
)


# ---------------------------------------------------------------------------
# Sensitive resource markers
# ---------------------------------------------------------------------------
SENSITIVE_RESOURCE_MARKERS: tuple[str, ...] = (
    "credential",
    "secret",
    "password",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "customer",
    "pii",
    "ssn",
    "billing",
    "invoice",
    "payroll",
)


# ---------------------------------------------------------------------------
# Prompt-injection markers (heuristic, argument-level)
# ---------------------------------------------------------------------------
INJECTION_MARKERS: tuple[str, ...] = (
    "ignore previous",
    "ignore the user",
    "ignore all previous",
    "disregard the user",
    "system prompt",
    "new instructions",
    "as an ai",
    "you must now",
    "override the",
    "forget your instructions",
    "developer mode",
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _iter_strings(value: Any) -> Iterable[str]:
    """Recursively yield every string contained in `value`."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _iter_strings(v)


def match_any(patterns: Iterable[Pattern[str]], text: str) -> list[str]:
    """Return the list of pattern source strings that matched `text`."""
    hits: list[str] = []
    for pattern in patterns:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def scan_for_sql_injection(text: str) -> list[str]:
    return match_any(SQL_INJECTION_PATTERNS, text)


def scan_for_command_injection(text: str) -> list[str]:
    return match_any(COMMAND_INJECTION_PATTERNS, text)


def contains_path_traversal(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in PATH_TRAVERSAL_MARKERS)


def contains_injection_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def looks_like_private_host(host: str) -> bool:
    if not host:
        return True
    host = host.strip().strip("[]").lower()
    if host in METADATA_HOSTS:
        return True
    return any(p.search(host) for p in PRIVATE_IP_PATTERNS)


def classify_operation_keywords(*texts: str) -> dict[str, bool]:
    """Classify a set of strings against destructive/high-impact/irreversible cues."""
    blob = " ".join(texts).lower()
    tokens = set(re.split(r"[^a-z0-9_]+", blob))
    return {
        "destructive": bool(tokens & DESTRUCTIVE_KEYWORDS),
        "high_impact": bool(tokens & HIGH_IMPACT_KEYWORDS),
        "irreversible": bool(tokens & IRREVERSIBLE_KEYWORDS),
    }


def is_sensitive_resource(name: str) -> bool:
    if not name:
        return False
    lowered = name.lower()
    return any(marker in lowered for marker in SENSITIVE_RESOURCE_MARKERS)


def scan_all_arguments(arguments: dict[str, Any]) -> dict[str, list[str]]:
    """Return a map of finding-category → matched pattern strings."""
    sql_hits: list[str] = []
    cmd_hits: list[str] = []
    traversal_hits: list[str] = []
    injection_hits: list[str] = []

    for text in _iter_strings(arguments):
        sql_hits.extend(scan_for_sql_injection(text))
        cmd_hits.extend(scan_for_command_injection(text))
        if contains_path_traversal(text):
            traversal_hits.append(text[:64])
        if contains_injection_marker(text):
            injection_hits.append(text[:64])

    def _uniq(seq: list[str]) -> list[str]:
        return list(dict.fromkeys(seq))

    return {
        "sql_injection": _uniq(sql_hits),
        "command_injection": _uniq(cmd_hits),
        "path_traversal": _uniq(traversal_hits),
        "injection_marker": _uniq(injection_hits),
    }