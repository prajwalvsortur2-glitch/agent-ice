"""Live monitor page: latest decisions with a compact flow diagram."""
from __future__ import annotations

import time

import streamlit as st

from dashboard.components.attack_flow import render_attack_flow, render_compact_flow
from dashboard.components.decision_card import render_decision_card
from dashboard.utils import (
    backend_reachable,
    fetch_audit,
    fetch_incidents,
    fmt_relative,
)


def _stage_from_event(event: dict) -> dict:
    """Build an attack-flow stage dict from an audit event."""
    detail = event.get("detail") or {}
    provenance = detail.get("provenance") or []
    provenance_summary = ", ".join(
        f"{p.get('trust_level','?')}:{p.get('source_id','?')}" for p in provenance
    ) or "no provenance"
    return {
        "user_intent": detail.get("user_intent") or "(not recorded)",
        "agent_name": "qwen-agent",
        "tool_name": event.get("tool_name") or "-",
        "inspection_id": detail.get("inspection_id") or "-",
        "provenance_summary": provenance_summary,
        "risk_summary": f"{event.get('risk_level','-')} · {event.get('risk_score','-')}/100",
        "decision": event.get("decision") or "-",
    }


def render() -> None:
    st.title("Live Monitor")
    st.caption("Every recent inspection decision, rendered as a flow.")

    if not backend_reachable():
        st.error("Backend is not reachable.")
        return

    col_refresh, col_auto, col_limit = st.columns([1, 1, 2])
    with col_refresh:
        if st.button("Refresh now"):
            st.cache_data.clear()
    with col_auto:
        auto = st.toggle("Auto-refresh", value=False)
    with col_limit:
        limit = st.slider("Events to display", min_value=5, max_value=100, value=25, step=5)

    audit = fetch_audit(limit=limit)
    events = audit.get("events") or []

    if not events:
        st.info("No events to display yet. Run the demo from another window.")
        return

    st.markdown(f"**{len(events)} recent events**")

    # Show as a scrollable list of cards.
    for event in events:
        decision = event.get("decision") or "-"
        tool = event.get("tool_name") or "-"
        ts = fmt_relative(event.get("timestamp"))
        risk_level = event.get("risk_level") or "-"
        risk_score = event.get("risk_score") or 0

        with st.container():
            top_left, top_right = st.columns([3, 1])
            with top_left:
                st.markdown(
                    f"**{event.get('event_type','-')}** · "
                    f"`{tool}` · *{ts}*"
                )
                render_compact_flow(decision)
            with top_right:
                st.caption(f"session `{(event.get('session_id') or '-')[:12]}…`")
                st.caption(f"latency `{event.get('latency_ms','-')} ms`")

            with st.expander("Open flow"):
                stage = _stage_from_event(event)
                render_attack_flow(stage)

                if decision in {"BLOCK", "RESTRICT", "REVIEW"}:
                    # Pull the incident detail for the same session.
                    incidents = fetch_incidents(
                        session_id=event.get("session_id"), limit=10
                    ).get("incidents") or []
                    match = next(
                        (i for i in incidents if i.get("tool_name") == tool), None
                    )
                    if match:
                        render_decision_card(
                            decision=match.get("decision", decision),
                            risk_score=match.get("risk_score", risk_score),
                            risk_level=match.get("risk_level", risk_level),
                            explanation=match.get("explanation", ""),
                            reason_codes=match.get("reason_codes") or [],
                            tool_name=match.get("tool_name", tool),
                        )
            st.markdown(
                '<hr style="border:none;border-top:1px solid rgba(100,116,139,0.2);'
                'margin:6px 0 12px 0;">',
                unsafe_allow_html=True,
            )

    if auto:
        time.sleep(5)
        st.rerun()