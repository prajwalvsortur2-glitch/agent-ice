"""FastAPI dependency providers for Agent ICE.

Why this file exists
--------------------
FastAPI routes must stay thin. They should never construct security engines
inline, never instantiate the ICE controller themselves, and never touch the
database engine directly. Instead, every route declares what it needs and this
module supplies it.

Design rules
------------
1.  All providers are callable with no required arguments so they can be used
    directly as `Depends(...)` targets.
2.  Heavy services (ICE controller, policy engine, tool registry) are cached
    process-wide via `lru_cache` — they are stateless or thread-safe.
3.  The SQLAlchemy `Session` is NOT cached: one session per request, closed
    in a `finally` block.
4.  Imports of engine/controller modules are performed lazily inside the
    factory functions. This keeps `app.dependencies` importable even when the
    rest of the tree is being assembled, avoids import cycles (controllers
    depend on many engines, some engines depend on `get_settings`), and makes
    tests easier to isolate.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Generator

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.storage.database import get_session_factory

if TYPE_CHECKING:
    # Type hints only — never imported at runtime to avoid cycles.
    from app.agent.agent import AgentService
    from app.ice.action_receipt import ReceiptService
    from app.ice.capability_engine import CapabilityEngine
    from app.ice.containment import ContainmentEngine
    from app.ice.controller import ICEController
    from app.ice.drift_engine import DriftEngine
    from app.ice.enforcement import EnforcementService
    from app.ice.intent_anchor import IntentAnchorService
    from app.ice.policy_engine import PolicyEngine
    from app.ice.provenance import ProvenanceLedger
    from app.ice.risk_engine import RiskEngine
    from app.llm.qwen_analyzer import QwenAnalyzer
    from app.storage.audit_repository import AuditRepository
    from app.tools.base_tool import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def get_settings_dep() -> Settings:
    """Return the cached settings singleton.

    Thin wrapper so route signatures read `Depends(get_settings_dep)` rather
    than importing the config module directly.
    """
    return get_settings()


# ---------------------------------------------------------------------------
# Database session (per request)
# ---------------------------------------------------------------------------
def get_db_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and guarantee it is closed afterwards.

    This intentionally does NOT cache. Each HTTP request gets a fresh session.
    """
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Audit repository
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_audit_repository() -> "AuditRepository":
    """Process-wide audit repository (stateless, thread-safe)."""
    from app.storage.audit_repository import AuditRepository

    return AuditRepository()


# ---------------------------------------------------------------------------
# ICE engines (all stateless / config-driven → safe to cache)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_intent_anchor_service() -> "IntentAnchorService":
    from app.ice.intent_anchor import IntentAnchorService

    return IntentAnchorService()


@lru_cache(maxsize=1)
def get_provenance_ledger() -> "ProvenanceLedger":
    from app.ice.provenance import ProvenanceLedger

    return ProvenanceLedger()


@lru_cache(maxsize=1)
def get_capability_engine() -> "CapabilityEngine":
    from app.ice.capability_engine import CapabilityEngine

    return CapabilityEngine(settings=get_settings())


@lru_cache(maxsize=1)
def get_policy_engine() -> "PolicyEngine":
    from app.ice.policy_engine import PolicyEngine

    return PolicyEngine(
        settings=get_settings(),
        policies_dir=get_settings().policies_dir,
    )


@lru_cache(maxsize=1)
def get_risk_engine() -> "RiskEngine":
    from app.ice.risk_engine import RiskEngine

    return RiskEngine(settings=get_settings())


@lru_cache(maxsize=1)
def get_qwen_analyzer() -> "QwenAnalyzer":
    from app.llm.qwen_analyzer import QwenAnalyzer

    return QwenAnalyzer(settings=get_settings())


@lru_cache(maxsize=1)
def get_drift_engine() -> "DriftEngine":
    from app.ice.drift_engine import DriftEngine

    return DriftEngine(
        settings=get_settings(),
        qwen_analyzer=get_qwen_analyzer(),
    )


@lru_cache(maxsize=1)
def get_containment_engine() -> "ContainmentEngine":
    from app.ice.containment import ContainmentEngine

    return ContainmentEngine()


@lru_cache(maxsize=1)
def get_receipt_service() -> "ReceiptService":
    from app.ice.action_receipt import ReceiptService

    return ReceiptService(settings=get_settings())


@lru_cache(maxsize=1)
def get_enforcement_service() -> "EnforcementService":
    from app.ice.enforcement import EnforcementService

    return EnforcementService()


# ---------------------------------------------------------------------------
# Tool registry (safe mock tools only)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_tool_registry() -> "ToolRegistry":
    """Return the singleton registry containing all safe mock tools.

    Registration happens here rather than in a decorator so the set of
    available tools is discoverable in one place. Tests may swap individual
    tools via the registry's `register`/`get` methods.
    """
    from app.tools.base_tool import ToolRegistry
    from app.tools.http_tool import HttpFetchTool
    from app.tools.communication_tool import SendEmailTool
    from app.tools.database_tool import QueryDatabaseTool
    from app.tools.email_tool import ReadEmailTool
    from app.tools.file_tool import ReadFileTool
    from app.tools.record_tool import DeleteRecordTool

    registry = ToolRegistry()
    registry.register(ReadEmailTool())
    registry.register(ReadFileTool())
    registry.register(QueryDatabaseTool())
    registry.register(SendEmailTool())
    registry.register(DeleteRecordTool())
    registry.register(HttpFetchTool())
    logger.info("Tool registry initialized with %d tools", len(registry))
    return registry


# ---------------------------------------------------------------------------
# ICE controller (the trusted enforcement boundary)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_ice_controller() -> "ICEController":
    """Wire every engine into the single ICE controller.

    Routes NEVER call these engines directly for a security decision. They
    call this controller. Keeping the composition in one place makes the
    trust boundary auditable.
    """
    from app.ice.controller import ICEController

    return ICEController(
        settings=get_settings(),
        intent_anchor=get_intent_anchor_service(),
        provenance=get_provenance_ledger(),
        capabilities=get_capability_engine(),
        policy=get_policy_engine(),
        risk=get_risk_engine(),
        drift=get_drift_engine(),
        containment=get_containment_engine(),
        receipts=get_receipt_service(),
        enforcement=get_enforcement_service(),
        audit=get_audit_repository(),
        tool_registry=get_tool_registry(),
    )


# ---------------------------------------------------------------------------
# Agent service (the untrusted planner / proposal source)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_agent_service() -> "AgentService":
    """Return the agent service.

    The agent *plans* and *proposes* tool calls. It has no authority to
    execute protected tools; every proposal must pass through ICE.
    """
    from app.agent.agent import AgentService

    return AgentService(
        settings=get_settings(),
        qwen_analyzer=get_qwen_analyzer(),
        intent_anchor=get_intent_anchor_service(),
        ice_controller=get_ice_controller(),
        tool_registry=get_tool_registry(),
    )


# ---------------------------------------------------------------------------
# Cache reset helpers (used by tests and reset scripts)
# ---------------------------------------------------------------------------
def reset_dependency_caches() -> None:
    """Clear every cached dependency.

    Call this between tests or after a database reset so a fresh set of
    engines picks up new configuration / policy files.
    """
    for fn in (
        get_settings_dep,
        get_audit_repository,
        get_intent_anchor_service,
        get_provenance_ledger,
        get_capability_engine,
        get_policy_engine,
        get_risk_engine,
        get_qwen_analyzer,
        get_drift_engine,
        get_containment_engine,
        get_receipt_service,
        get_enforcement_service,
        get_tool_registry,
        get_ice_controller,
        get_agent_service,
    ):
        try:
            fn.cache_clear()  # type: ignore[attr-defined]
        except AttributeError:
            # get_settings is separately cached in app.config.
            continue

    # Also clear the config-level cache so new env vars take effect.
    get_settings.cache_clear()