"""Overview page: live counters and system state."""
from __future__ import annotations

import streamlit as st

from dashboard.components.event_table import render_kpi_row, render_status_row
from dashboard.utils import (
    backend_reachable,
    decision_counts,
    fetch_audit,
    fetch_health,
    fetch_incidents,
    fetch_ollama_health,
)


def render() -> None:
    st.title("Overview")
    st.caption("Live state of the Agent ICE security controller.")

    if not backend_reachable():
        st.error(
            "Backend is not reachable. Start it with `scripts\\windows\\start.ps1` "
            "and refresh this page."
        )
        return

    health = fetch_health()
    ollama = fetch_ollama_health()

    # --- Component health -------------------------------------------------
    components = health.get("components", {}) or {}
    render_status_row(
        {
            "API": "HEALTHY",
            "DATABASE": components.get("database", "UNKNOWN"),
            "OLLAMA": components.get("ollama", "UNKNOWN"),
            "QWEN": components.get("qwen", "UNKNOWN"),
            "ICE": components.get("ice", "ACTIVE"),
        }
    )

    st.markdown("---")

    # --- Counters from real data -----------------------------------------
    audit = fetch_audit(limit=500)
    events = audit.get("events") or []
    counts = decision_counts(events)

    # Sessions seen in the audit window (approximation of "active").
    sessions = {e.get("session_id") for e in events if e.get("session_id")}

    render_kpi_row(
        {
            "Sessions (recent)": len(sessions),
            "Actions Inspected": len(events),
            "Allowed": counts["ALLOW"],
            "Review": counts["REVIEW"],
            "Restricted": counts["RESTRICT"],
            "Blocked": counts["BLOCK"],
        }
    )

    st.markdown("---")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("Recent activity")
        # Show a compact list of the most recent events.
        recent = events[:15]
        if not recent:
            st.info("No security events recorded yet.")
        else:
            for e in recent:
                d = e.get("decision") or "-"
                color = {
                    "ALLOW": "#16a34a",
                    "REVIEW": "#eab308",
                    "RESTRICT": "#f97316",
                    "BLOCK": "#dc2626",
                }.get(d, "#64748b")
                st.markdown(
                    f"""
                    <div style="display:flex;justify-content:space-between;
                                padding:8px 12px;border-bottom:1px solid
                                rgba(100,116,139,0.2);">
                        <div>
                            <span style="font-size:12px;color:#94a3b8;">
                                {e.get('event_type','-')}</span>
                            <span style="font-size:13px;color:#e2e8f0;margin-left:8px;">
                                <code>{e.get('tool_name','-')}</code></span>
                            <div style="font-size:11px;color:#64748b;margin-top:2px;">
                                {e.get('session_id','-')} · {e.get('timestamp','-')}</div>
                        </div>
                        <div style="text-align:right;">
                            <span style="background:{color};color:white;
                                         padding:2px 10px;border-radius:999px;
                                         font-size:11px;font-weight:700;">
                                {d}</span>
                            <div style="font-size:11px;color:#94a3b8;margin-top:2px;">
                                risk {e.get('risk_score','-')}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col_right:
        st.subheader("System")
        st.markdown(
            f"""
            - **App env**: `{health.get('app_env','-')}`
            - **Version**: `{health.get('version','-')}`
            - **Status**: `{health.get('status','-')}`
            - **Ollama URL**: `{ollama.get('base_url','-')}`
            - **Model**: `{ollama.get('model','-')}`
            - **Model available**: `{ollama.get('model_available','-')}`
            """
        )
        incidents = fetch_incidents(limit=1).get("total", 0)
        st.metric("Total incidents", incidents)