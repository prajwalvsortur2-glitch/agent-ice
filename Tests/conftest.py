from __future__ import annotations

import pytest


@pytest.fixture
def capabilities_dict() -> dict[str, bool]:
    return {
        "email.read": True,
        "filesystem.read": True,
        "database.read": True,
        "email.send": False,
        "database.delete": False,
    }


@pytest.fixture
def minimal_policy() -> dict:
    return {
        "tools": {
            "allowlist": ["read_email", "read_file", "query_database", "send_email", "delete_record"],
            "high_impact": ["send_email", "delete_record"],
        },
        "resources": {
            "sensitive_markers": ["customer", "billing", "payroll", "credential", "secret"],
            "path_allowlist": ["data/fixtures/files", "reports"],
        },
        "network": {"domain_allowlist": ["company.local", "internal.company.local"]},
        "email": {"internal_domains": ["company.local"]},
        "risk": {"thresholds": {"low_max": 24, "medium_max": 49, "high_max": 79}},
    }


@pytest.fixture
def risk_weights() -> dict[str, int]:
    return {
        "intent_mismatch_low": 15,
        "intent_mismatch_high": 35,
        "untrusted_provenance": 25,
        "restricted_provenance": 5,
        "sensitive_resource": 15,
        "external_destination": 25,
        "high_impact_operation": 20,
        "destructive_operation": 30,
        "irreversible_operation": 20,
        "credential_access": 30,
        "policy_violation": 20,
        "path_traversal": 40,
        "sql_injection": 40,
        "command_injection": 40,
        "ssrf": 40,
    }


@pytest.fixture
def risk_thresholds() -> dict[str, int]:
    return {"low_max": 24, "medium_max": 49, "high_max": 79}


@pytest.fixture
def receipt_secret() -> str:
    return "a-very-long-test-secret-for-receipts-1234567890"


@pytest.fixture
def receipt_ttl() -> int:
    return 30
