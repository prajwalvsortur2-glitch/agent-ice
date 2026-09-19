"""Minimal synchronous HTTP client for local Ollama.

We intentionally do not use a third-party Ollama wrapper: a tiny httpx client
is easier to audit and avoids pulling in a dependency that might not respect
the local-only requirement.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OllamaError(RuntimeError):
    """Raised for any failure communicating with Ollama."""


class OllamaClient:
    """Thin sync wrapper around the Ollama HTTP API."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = settings.ollama_timeout_seconds
        self._max_retries = max(0, settings.ollama_max_retries)
        self._client = client or httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={"User-Agent": "agent-ice/0.1"},
        )

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def list_models(self) -> list[str]:
        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError(f"failed to list models: {exc}") from exc
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]

    def is_model_available(self) -> bool:
        try:
            names = self.list_models()
        except OllamaError:
            return False
        return any(n == self._model or n.startswith(self._model + ":") for n in names)

    def health(self) -> dict[str, Any]:
        try:
            names = self.list_models()
        except OllamaError as exc:
            return {
                "reachable": False,
                "base_url": self._base_url,
                "model": self._model,
                "model_available": False,
                "detail": str(exc),
            }
        available = any(n == self._model or n.startswith(self._model + ":") for n in names)
        return {
            "reachable": True,
            "base_url": self._base_url,
            "model": self._model,
            "model_available": available,
            "detail": None if available else f"model {self._model!r} not installed",
        }

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        """Return the raw text output from Ollama. Raises OllamaError on failure."""
        body: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            body["system"] = system

        last_exc: Exception | None = None
        for attempt in range(1 + self._max_retries):
            try:
                resp = self._client.post("/api/generate", json=body)
                resp.raise_for_status()
                payload = resp.json()
                text = payload.get("response", "")
                if not isinstance(text, str):
                    raise OllamaError("malformed response: 'response' is not a string")
                return text
            except (httpx.HTTPError, ValueError, OllamaError) as exc:
                last_exc = exc
                logger.warning(
                    "Ollama generate attempt %d/%d failed: %s",
                    attempt + 1,
                    1 + self._max_retries,
                    exc,
                )
        raise OllamaError(f"ollama generate failed after retries: {last_exc}")

    def close(self) -> None:
        self._client.close()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"OllamaClient(base_url={self._base_url!r}, model={self._model!r})"


def dumps_for_debug(obj: Any) -> str:
    """Helper used by tests and debug logs."""
    return json.dumps(obj, default=str, indent=2)