"""HMAC-SHA256 action receipts.

A receipt binds an authorization to the exact tool call that was inspected.
Any change to session, tool, arguments, resource, capability or decision
invalidates it. Any expiry or reuse fails verification.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.ice.decision import Decision
from app.models import ToolCall
from app.storage.audit_repository import canonical_arguments_hash

logger = logging.getLogger(__name__)


class ReceiptError(RuntimeError):
    """Raised when a receipt fails verification."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class ActionReceipt:
    session_id: str
    intent_hash: str
    tool_name: str
    arguments: dict[str, Any]
    resource: str | None
    capability: str | None
    decision: str
    issued_at: float
    expires_at: float
    nonce: str
    signature: str

    @property
    def arguments_hash(self) -> str:
        return canonical_arguments_hash(self.arguments)


@dataclass(frozen=True)
class IssuedReceipt:
    receipt_id: str
    token: str
    expires_at: datetime


class ReceiptSigner:
    def __init__(self, secret: str, ttl_seconds: int | float = 30) -> None:
        self.secret = secret
        self.ttl_seconds = int(ttl_seconds)

    def _sign_payload(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    def issue(
        self,
        *,
        session_id: str,
        intent_hash: str,
        tool_name: str,
        arguments: dict[str, Any],
        resource: str | None,
        capability: str | None,
        decision: str,
    ) -> ActionReceipt:
        issued_at = datetime.now(timezone.utc).timestamp()
        expires_at = issued_at + self.ttl_seconds
        nonce = secrets.token_hex(16)
        payload = {
            "session_id": session_id,
            "intent_hash": intent_hash,
            "tool_name": tool_name,
            "arguments": arguments,
            "resource": resource,
            "capability": capability,
            "decision": decision,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "nonce": nonce,
        }
        signature = self._sign_payload(payload)
        return ActionReceipt(
            session_id=session_id,
            intent_hash=intent_hash,
            tool_name=tool_name,
            arguments=dict(arguments),
            resource=resource,
            capability=capability,
            decision=decision,
            issued_at=issued_at,
            expires_at=expires_at,
            nonce=nonce,
            signature=signature,
        )

    def verify(
        self,
        receipt: ActionReceipt,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        if not isinstance(receipt, ActionReceipt):
            return False
        if receipt.tool_name != tool_name:
            return False
        if receipt.arguments != arguments:
            return False
        if receipt.expires_at <= datetime.now(timezone.utc).timestamp():
            return False

        payload = {
            "session_id": receipt.session_id,
            "intent_hash": receipt.intent_hash,
            "tool_name": receipt.tool_name,
            "arguments": receipt.arguments,
            "resource": receipt.resource,
            "capability": receipt.capability,
            "decision": receipt.decision,
            "issued_at": receipt.issued_at,
            "expires_at": receipt.expires_at,
            "nonce": receipt.nonce,
        }
        expected = self._sign_payload(payload)
        return hmac.compare_digest(receipt.signature, expected)


class ReceiptService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._secret = settings.receipt_secret.encode("utf-8")
        self._ttl_seconds = int(settings.receipt_ttl_seconds)

    # ------------------------------------------------------------------
    # Issuance
    # ------------------------------------------------------------------
    def issue(
        self,
        *,
        session_id: str,
        inspection_id: str,
        intent_hash: str,
        tool_call: ToolCall,
        resource: str | None,
        capability: str | None,
        decision: Decision,
        now: datetime | None = None,
    ) -> IssuedReceipt:
        receipt_id = str(uuid.uuid4())
        issued_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expires_at = issued_at + timedelta(seconds=self._ttl_seconds)
        nonce = secrets.token_hex(16)

        payload: dict[str, Any] = {
            "receipt_id": receipt_id,
            "session_id": session_id,
            "inspection_id": inspection_id,
            "intent_hash": intent_hash,
            "tool_name": tool_call.tool_name,
            "arguments_hash": canonical_arguments_hash(tool_call.arguments),
            "resource": resource,
            "capability": capability,
            "decision": decision.value,
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "nonce": nonce,
        }
        signature = self._sign(payload)
        token = self._encode(payload, signature)
        return IssuedReceipt(receipt_id=receipt_id, token=token, expires_at=expires_at)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------
    def verify(
        self,
        *,
        token: str,
        session_id: str,
        intent_hash: str,
        tool_call: ToolCall,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Verify signature, binding, and expiry. Returns the payload."""
        if not isinstance(token, str) or not token:
            raise ReceiptError("RECEIPT_MISSING", "receipt token is missing")

        payload, signature = self._decode(token)
        expected = self._sign(payload)
        if not hmac.compare_digest(expected, signature):
            raise ReceiptError("RECEIPT_INVALID", "receipt signature does not match")

        # Binding checks.
        if payload.get("session_id") != session_id:
            raise ReceiptError("RECEIPT_MISMATCH", "session_id mismatch")
        if payload.get("intent_hash") != intent_hash:
            raise ReceiptError("RECEIPT_MISMATCH", "intent_hash mismatch")
        if payload.get("tool_name") != tool_call.tool_name:
            raise ReceiptError("RECEIPT_MISMATCH", "tool_name mismatch")
        actual_args_hash = canonical_arguments_hash(tool_call.arguments)
        if payload.get("arguments_hash") != actual_args_hash:
            raise ReceiptError("RECEIPT_MISMATCH", "arguments_hash mismatch")
        if payload.get("decision") != Decision.ALLOW.value and payload.get("decision") != Decision.RESTRICT.value:
            # Only ALLOW and RESTRICT receipts are executable.
            raise ReceiptError("RECEIPT_INVALID", "receipt was not issued for an executable decision")

        # Expiry check.
        expires_raw = payload.get("expires_at")
        try:
            expires_at = datetime.fromisoformat(expires_raw)
        except (TypeError, ValueError) as exc:
            raise ReceiptError("RECEIPT_INVALID", f"invalid expires_at: {exc}") from exc
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if current > expires_at:
            raise ReceiptError("RECEIPT_EXPIRED", "receipt has expired")

        return payload

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _sign(self, payload: dict[str, Any]) -> str:
        message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()

    @staticmethod
    def _encode(payload: dict[str, Any], signature: str) -> str:
        envelope = {"payload": payload, "signature": signature}
        raw = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    @staticmethod
    def _decode(token: str) -> tuple[dict[str, Any], str]:
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii"))
            envelope = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ReceiptError("RECEIPT_INVALID", f"token is not decodable: {exc}") from exc
        payload = envelope.get("payload")
        signature = envelope.get("signature")
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ReceiptError("RECEIPT_INVALID", "token envelope is malformed")
        return payload, signature