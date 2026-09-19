"""Agent ICE FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.storage.database import init_db
from app.telemetry.logger import configure_logging

logger = logging.getLogger("agent_ice.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.is_using_insecure_default_secret():
        logger.warning(
            "RECEIPT_SECRET is using the insecure default. Set a strong random value in .env."
        )

    init_db()
    logger.info("Agent ICE starting (env=%s)", settings.app_env)

    # Warn (do not fail) if Ollama is not reachable; fail-closed behavior
    # handles high-risk requests correctly without it.
    try:
        from app.dependencies import get_qwen_analyzer

        h = get_qwen_analyzer().health()
        if not h.get("reachable"):
            logger.warning("Ollama is not reachable: %s", h.get("detail"))
        elif not h.get("model_available"):
            logger.warning("Ollama model is not installed: %s", h.get("model"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("could not query Ollama health: %s", exc)

    yield

    logger.info("Agent ICE shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    frontend_origin = urlsplit(settings.frontend_origin)
    loopback_host = {
        "localhost": "127.0.0.1",
        "127.0.0.1": "localhost",
    }.get(frontend_origin.hostname)
    allowed_origins = [settings.frontend_origin]
    if loopback_host:
        allowed_origins.append(
            urlunsplit(
                (
                    frontend_origin.scheme,
                    loopback_host
                    + (f":{frontend_origin.port}" if frontend_origin.port else ""),
                    frontend_origin.path,
                    frontend_origin.query,
                    frontend_origin.fragment,
                )
            )
        )

    app = FastAPI(
        title="Agent ICE",
        description="Intent-to-Action Security Controller for AI agents.",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Routers — imported lazily so a missing optional dependency does not
    # prevent the app from starting for /health.
    from app.api.routes_agent import router as agent_router
    from app.api.routes_audit import router as audit_router
    from app.api.routes_health import router as health_router
    from app.api.routes_ice import router as ice_router
    from app.api.routes_tools import router as tools_router

    app.include_router(health_router)
    app.include_router(ice_router)
    app.include_router(agent_router)
    app.include_router(tools_router)
    app.include_router(audit_router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": "Agent ICE",
            "full_name": "Intent-to-Action Security Controller",
            "version": __version__,
            "docs": "/docs",
        }

    return app


app = create_app()