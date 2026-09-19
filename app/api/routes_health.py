"""Health endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app import __version__
from app.config import Settings
from app.dependencies import get_qwen_analyzer, get_settings_dep
from app.schemas import HealthResponse, OllamaHealthResponse
from app.storage.audit_repository import AuditRepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings_dep)) -> HealthResponse:
    components: dict[str, str] = {}

    # Database
    try:
        repo = AuditRepository()
        repo.stats()
        components["database"] = "HEALTHY"
    except Exception as exc:  # noqa: BLE001
        logger.warning("database health check failed: %s", exc)
        components["database"] = "UNHEALTHY"

    # Ollama (best-effort; do not fail the overall health if absent)
    try:
        analyzer = get_qwen_analyzer()
        h = analyzer.health()
        components["ollama"] = "HEALTHY" if h.get("reachable") else "UNREACHABLE"
        components["qwen"] = "READY" if h.get("model_available") else "MODEL_MISSING"
    except Exception as exc:  # noqa: BLE001
        logger.warning("ollama health check failed: %s", exc)
        components["ollama"] = "UNREACHABLE"
        components["qwen"] = "UNKNOWN"

    components["ice"] = "ACTIVE"

    overall = "ok" if components.get("database") == "HEALTHY" else "degraded"
    return HealthResponse(
        status=overall,
        app_env=settings.app_env,
        version=__version__,
        components=components,
        fail_closed=settings.ice_fail_closed,
    )


@router.get("/health/ollama", response_model=OllamaHealthResponse)
def ollama_health() -> OllamaHealthResponse:
    analyzer = get_qwen_analyzer()
    h = analyzer.health()
    return OllamaHealthResponse(
        reachable=bool(h.get("reachable")),
        base_url=h.get("base_url", ""),
        model=h.get("model", ""),
        model_available=bool(h.get("model_available")),
        detail=h.get("detail"),
    )