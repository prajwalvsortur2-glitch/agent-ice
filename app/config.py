"""Application configuration loaded from environment variables.

All configurable values for Agent ICE live here so they are never scattered
through the codebase. This module exposes a single cached `Settings` instance
via `get_settings()`.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_INSECURE_DEFAULT_SECRET = "CHANGE_ME_WITH_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARS"


class Settings(BaseSettings):
    """Runtime settings. Values come from environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ----------------------------------------------------------
    app_env: Literal["development", "staging", "production"] = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    # --- Ollama / Qwen ----------------------------------------------------
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_seconds: float = 60.0
    ollama_max_retries: int = 2

    # --- Persistence ------------------------------------------------------
    database_url: str = "sqlite:///./data/agent_ice.db"

    # --- ICE behavior -----------------------------------------------------
    ice_fail_closed: bool = True
    deep_analysis_risk_threshold: int = Field(default=40, ge=0, le=100)

    # --- Action receipts --------------------------------------------------
    receipt_secret: str = _INSECURE_DEFAULT_SECRET
    receipt_ttl_seconds: int = Field(default=30, ge=5, le=600)

    # --- CORS -------------------------------------------------------------
    frontend_origin: str = "http://localhost:5173"

    # --- Policies ---------------------------------------------------------
    policies_dir: str = "policies"

    @field_validator("receipt_secret")
    @classmethod
    def _validate_receipt_secret(cls, v: str) -> str:
        if not v or len(v) < 16:
            raise ValueError(
                "RECEIPT_SECRET must be at least 16 characters. "
                "Generate one with: python -c \"import secrets;print(secrets.token_urlsafe(48))\""
            )
        return v

    def is_using_insecure_default_secret(self) -> bool:
        return self.receipt_secret == _INSECURE_DEFAULT_SECRET


@lru_cache()
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    settings = Settings()
    if settings.is_using_insecure_default_secret():
        if settings.app_env == "production":
            raise RuntimeError(
                "RECEIPT_SECRET is still the insecure default. "
                "Refusing to start in production. Set RECEIPT_SECRET in .env."
            )
        logger.warning(
            "RECEIPT_SECRET is using the insecure default. "
            "Set a strong random value in .env before any real use."
        )
    return settings