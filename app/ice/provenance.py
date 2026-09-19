"""Provenance / taint ledger.

Message-and-argument level provenance. Not token-level taint tracking.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ice.decision import ReasonCode
from app.models import ProvenanceRef, ToolCall, TrustLevel
from app.security.dangerous_patterns import contains_injection_marker

logger = logging.getLogger(__name__)


# Trust classification per source type.
_SOURCE_TRUST: dict[str, TrustLevel] = {
    "user_prompt": TrustLevel.TRUSTED,
    "system_policy": TrustLevel.TRUSTED,
    "user": TrustLevel.TRUSTED,
    "system": TrustLevel.TRUSTED,
    "assistant": TrustLevel.TRUSTED,
    "agent": TrustLevel.TRUSTED,
    "model": TrustLevel.TRUSTED,
    "internal_data": TrustLevel.RESTRICTED,
    "authorized_internal_data": TrustLevel.RESTRICTED,
    "email": TrustLevel.UNTRUSTED,
    "email_content": TrustLevel.UNTRUSTED,
    "web": TrustLevel.UNTRUSTED,
    "web_content": TrustLevel.UNTRUSTED,
    "external_tool_result": TrustLevel.UNTRUSTED,
    "tool_result": TrustLevel.UNTRUSTED,
    "attachment": TrustLevel.UNTRUSTED,
    "unknown": TrustLevel.UNTRUSTED,
}


@dataclass(frozen=True)
class ProvenanceSource:
    source_id: str
    source_type: str
    trust_level: TrustLevel


class ProvenanceLedger:
    """Classifies sources, builds refs, and detects obvious manipulation."""

    def __init__(self) -> None:
        self._sources: list[ProvenanceSource] = []

    def add(self, source: ProvenanceSource) -> None:
        if any(s.source_id == source.source_id for s in self._sources):
            return
        self._sources.append(source)

    def sources(self) -> list[ProvenanceSource]:
        return list(self._sources)

    def aggregate_trust(self) -> TrustLevel:
        if any(s.trust_level == TrustLevel.UNTRUSTED for s in self._sources):
            return TrustLevel.UNTRUSTED
        if any(s.trust_level == TrustLevel.RESTRICTED for s in self._sources):
            return TrustLevel.RESTRICTED
        return TrustLevel.TRUSTED

    def has_untrusted(self) -> bool:
        return any(s.trust_level == TrustLevel.UNTRUSTED for s in self._sources)

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {"sources": [{"source_id": s.source_id, "source_type": s.source_type, "trust_level": s.trust_level.value} for s in self._sources]}

    def classify_source(self, source_type: str) -> TrustLevel:
        normalized = (source_type or "").strip().lower()
        return _SOURCE_TRUST.get(normalized, TrustLevel.UNTRUSTED)

    def build_ref(self, source_id: str, source_type: str) -> ProvenanceRef:
        return ProvenanceRef(
            source_id=source_id,
            source_type=source_type,
            trust_level=self.classify_source(source_type),
        )

    def summarize(self, provenance: list[ProvenanceRef]) -> dict[str, int]:
        counts = {"TRUSTED": 0, "RESTRICTED": 0, "UNTRUSTED": 0}
        for ref in provenance:
            counts[ref.trust_level.value] += 1
        return counts

    def detect_manipulation(
        self,
        tool_call: ToolCall,
    ) -> tuple[bool, list[str], list[str]]:
        """Return (suspicious, reasons, reason_codes).

        Detects a narrow set of provenance-manipulation patterns:
          * untrusted-sourced arguments that contain instruction markers
          * untrusted-sourced arguments that claim authority or override
          * claims of "trusted" provenance without a trusted source type
        """
        reasons: list[str] = []
        codes: list[str] = []
        suspicious = False

        untrusted = [p for p in tool_call.provenance if p.trust_level == TrustLevel.UNTRUSTED]

        # 1. Instruction-like text in untrusted arguments.
        if untrusted:
            for text in _iter_strings(tool_call.arguments):
                if contains_injection_marker(text):
                    suspicious = True
                    reasons.append(
                        "untrusted provenance carried instruction-like text in arguments"
                    )
                    codes.append(ReasonCode.PROVENANCE_MANIPULATION)
                    break

        # 2. Trusted source that is not a known trusted source type.
        trusted_source_types = {
            "user_prompt",
            "system_policy",
            "user",
            "system",
            "assistant",
            "agent",
            "model",
        }
        for ref in tool_call.provenance:
            if ref.trust_level == TrustLevel.TRUSTED:
                if ref.source_type.lower() not in trusted_source_types:
                    suspicious = True
                    reasons.append(
                        f"source {ref.source_id!r} claims TRUSTED but has source_type "
                        f"{ref.source_type!r}"
                    )
                    codes.append(ReasonCode.PROVENANCE_MANIPULATION)

        return suspicious, reasons, list(dict.fromkeys(codes))


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _iter_strings(v)