"""Thin wrapper around IntentAnchorService used by the agent layer.

Kept in a separate module so the agent never imports the ICE service
directly: the agent depends on the *interface*, and the composition root
(`app.dependencies`) decides which implementation is injected.
"""
from __future__ import annotations

from app.ice.intent_anchor import IntentAnchorService
from app.models import IntentAnchor


class IntentBootstrap:
    def __init__(self, service: IntentAnchorService) -> None:
        self._service = service

    def build(self, user_intent: str) -> tuple[IntentAnchor, str]:
        return self._service.bootstrap(user_intent)

    @staticmethod
    def compute_hash(anchor: IntentAnchor) -> str:
        return IntentAnchorService.compute_hash(anchor)