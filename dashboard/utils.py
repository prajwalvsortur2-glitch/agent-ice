"""Shared helpers for the Agent ICE dashboard.

  * A thin HTTP client for the backend API (read-only).
  * Formatting utilities (timestamps, risk colors, decision colors).
  * Cached fetchers keyed by the backend base URL.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def backend_base_url() -> str:
    """Resolve the backend base URL from env or fall back to localhost."""
    return os.environ.get("AGENT_ICE_BACKEND", "http://127.0.0.1:8000").rstrip("/")


def _http_get(path: str, params: Optional[dict[str, Any]] = None, timeout: float = 8.0) -> dict:
    url = f"{backend_base_url()}{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Cached fetchers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=2, show_spinner=False)
def fetch_health() -> dict:
    return _http_get("/health")


@st.cache_data(ttl=2, show_spinner=False)
def fetch_ollama_health() -> dict:
    return _http_get("/health/ollama")


@st.cache_data(ttl=3, show_spinner=False)
def fetch_audit(
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if session_id:
        params["session_id"] = session_id
    if event_type:
        params["event_type"] = event_type
    if decision:
        params["decision"] = decision
    return _http_get("/v1/audit", params=params)


@st.cache_data(ttl=3, show_spinner=False)
def fetch_incidents(
    session_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if session_id:
        params["session_id"] = session_id
    if risk_level:
        params["risk_level"] = risk_level
    if decision:
        params["decision"] = decision
    return _http_get("/v1/incidents", params=params)


@st.cache_data(ttl=10, show_spinner=False)
def fetch_policies() -> dict:
    return _http_get("/v1/policies")


@st.cache_data(ttl=30, show_spinner=False)
def fetch_tools() -> dict:
    return _http_get("/v1/tools")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------
def parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def fmt_ts(value: Any) -> str:
    dt = parse_ts(value)
    if dt is None:
        return "-"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fmt_relative(value: Any) -> str:
    dt = parse_ts(value)
    if dt is None:
        return "-"
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return "in the future"
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


DECISION_META = {
    "ALLOW":    {"emoji": "🟢", "label": "ALLOW",    "color": "#16a34a"},
    "REVIEW":   {"emoji": "🟡", "label": "REVIEW",   "color": "#eab308"},
    "RESTRICT": {"emoji": "🟠", "label": "RESTRICT", "color": "#f97316"},
    "BLOCK":    {"emoji": "🔴", "label": "BLOCK",    "color": "#dc2626"},
}

RISK_META = {
    "LOW":      {"emoji": "🟢", "color": "#16a34a"},
    "MEDIUM":   {"emoji": "🟡", "color": "#eab308"},
    "HIGH":     {"emoji": "🟠", "color": "#f97316"},
    "CRITICAL": {"emoji": "🚨", "color": "#dc2626"},
}


def decision_label(decision: Optional[str]) -> str:
    if not decision:
        return "-"
    meta = DECISION_META.get(decision, {"emoji": "⚪", "label": decision})
    return f"{meta['emoji']} {meta['label']}"


def risk_label(level: Optional[str]) -> str:
    if not level:
        return "-"
    meta = RISK_META.get(level, {"emoji": "⚪"})
    return f"{meta['emoji']} {level}"


def trust_label(level: Optional[str]) -> str:
    return {
        "TRUSTED":    "✅ TRUSTED",
        "RESTRICTED": "🟨 RESTRICTED",
        "UNTRUSTED":  "⚠️ UNTRUSTED",
    }.get(level or "", level or "-")


# ---------------------------------------------------------------------------
# Dataframe builders
# ---------------------------------------------------------------------------
def audit_to_dataframe(events: list[dict]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame(
            columns=[
                "timestamp", "event_type", "session_id", "tool_name",
                "decision", "risk_level", "risk_score", "reason_codes", "latency_ms",
            ]
        )
    rows = []
    for e in events:
        rows.append(
            {
                "timestamp": fmt_ts(e.get("timestamp")),
                "event_type": e.get("event_type") or "-",
                "session_id": e.get("session_id") or "-",
                "tool_name": e.get("tool_name") or "-",
                "decision": e.get("decision") or "-",
                "risk_level": e.get("risk_level") or "-",
                "risk_score": e.get("risk_score"),
                "reason_codes": ", ".join(e.get("reason_codes") or []),
                "latency_ms": round(e["latency_ms"], 2) if e.get("latency_ms") else None,
            }
        )
    return pd.DataFrame(rows)


def incidents_to_dataframe(incidents: list[dict]) -> pd.DataFrame:
    if not incidents:
        return pd.DataFrame(
            columns=[
                "incident_id", "created_at", "session_id", "tool_name",
                "risk_level", "risk_score", "decision", "reason_codes",
            ]
        )
    rows = []
    for i in incidents:
        rows.append(
            {
                "incident_id": i.get("incident_id", "-"),
                "created_at": fmt_ts(i.get("created_at")),
                "session_id": i.get("session_id", "-"),
                "tool_name": i.get("tool_name", "-"),
                "risk_level": i.get("risk_level", "-"),
                "risk_score": i.get("risk_score"),
                "decision": i.get("decision", "-"),
                "reason_codes": ", ".join(i.get("reason_codes") or []),
            }
        )
    return pd.DataFrame(rows)


def decision_counts(events: list[dict]) -> dict[str, int]:
    counts = {"ALLOW": 0, "REVIEW": 0, "RESTRICT": 0, "BLOCK": 0}
    for e in events:
        d = e.get("decision")
        if d in counts:
            counts[d] += 1
    return counts


def backend_reachable() -> bool:
    h = fetch_health()
    return "_error" not in h