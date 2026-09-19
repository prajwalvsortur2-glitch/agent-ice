"""Unit tests for Provenance / Taint Ledger.

Contract assumed from `app.ice.provenance`:

    class TrustLevel(str, Enum): TRUSTED | RESTRICTED | UNTRUSTED
    @dataclass(frozen=True) class ProvenanceSource:
        source_id: str
        source_type: str
        trust_level: TrustLevel
    class ProvenanceLedger:
        add(source) -> None
        sources() -> list[ProvenanceSource]
        aggregate_trust() -> TrustLevel
        has_untrusted() -> bool
        to_dict() -> dict
"""

from __future__ import annotations

import pytest

from app.ice.provenance import (
    ProvenanceLedger,
    ProvenanceSource,
    TrustLevel,
)


def test_trust_level_values():
    assert TrustLevel.TRUSTED.value == "TRUSTED"
    assert TrustLevel.RESTRICTED.value == "RESTRICTED"
    assert TrustLevel.UNTRUSTED.value == "UNTRUSTED"


def test_source_is_frozen():
    src = ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED)
    with pytest.raises(Exception):
        src.trust_level = TrustLevel.TRUSTED  # type: ignore[misc]


def test_ledger_starts_empty():
    ledger = ProvenanceLedger()
    assert ledger.sources() == []
    assert ledger.has_untrusted() is False


def test_ledger_adds_and_returns_sources():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED))
    ledger.add(ProvenanceSource("user_prompt", "user", TrustLevel.TRUSTED))
    ids = sorted(s.source_id for s in ledger.sources())
    assert ids == ["email_004", "user_prompt"]


def test_ledger_deduplicates_same_source_id():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED))
    ledger.add(ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED))
    assert len(ledger.sources()) == 1


def test_aggregate_trust_returns_lowest():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("user_prompt", "user", TrustLevel.TRUSTED))
    ledger.add(ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED))
    # Lowest wins -> UNTRUSTED
    assert ledger.aggregate_trust() == TrustLevel.UNTRUSTED
    assert ledger.has_untrusted() is True


def test_aggregate_trust_restricted_only():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("internal_db", "internal", TrustLevel.RESTRICTED))
    assert ledger.aggregate_trust() == TrustLevel.RESTRICTED
    assert ledger.has_untrusted() is False


def test_aggregate_trust_all_trusted():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("user_prompt", "user", TrustLevel.TRUSTED))
    assert ledger.aggregate_trust() == TrustLevel.TRUSTED


def test_to_dict_shape():
    ledger = ProvenanceLedger()
    ledger.add(ProvenanceSource("email_004", "email", TrustLevel.UNTRUSTED))
    d = ledger.to_dict()
    assert "sources" in d
    assert d["sources"][0]["source_id"] == "email_004"
    assert d["sources"][0]["trust_level"] == "UNTRUSTED"