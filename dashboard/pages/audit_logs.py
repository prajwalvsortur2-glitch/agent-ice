"""Audit logs page: search, filter and export events."""
from __future__ import annotations

import json

import streamlit as st

from dashboard.components.event_table import render_audit_table
from dashboard.utils import (
    audit_to_dataframe,
    backend_reachable,
    fetch_audit,
)


def render() -> None:
    st.title("Audit Logs")
    st.caption("Every security-relevant event recorded by Agent ICE.")

    if not backend_reachable():
        st.error("Backend is not reachable.")
        return

    # --- Filters ---------------------------------------------------------
    col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 2])
    with col_a:
        event_type = st.selectbox(
            "Event type",
            [
                "All",
                "inspect",
                "inspect_rejected",
                "execution",
                "execution_denied",
                "approval",
                "rejection",
                "restriction",
                "session_created",
            ],
            index=0,
        )
    with col_b:
        decision = st.selectbox("Decision", ["All", "ALLOW", "REVIEW", "RESTRICT", "BLOCK"], index=0)
    with col_c:
        session_filter = st.text_input("Session id contains", value="")
    with col_d:
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=300, step=25)

    params: dict = {"limit": int(limit)}
    if event_type != "All":
        params["event_type"] = event_type
    if decision != "All":
        params["decision"] = decision

    result = fetch_audit(**params)
    events = result.get("events") or []
    if session_filter:
        events = [
            e for e in events if session_filter.lower() in (e.get("session_id") or "").lower()
        ]

    st.markdown(f"**{len(events)} event(s)**")

    df = audit_to_dataframe(events)
    render_audit_table(df)

    # --- Export ---------------------------------------------------------
    st.markdown("---")
    st.subheader("Export")
    col_left, col_right = st.columns(2)
    with col_left:
        st.download_button(
            "Download as JSON",
            data=json.dumps(events, indent=2, default=str),
            file_name="agent_ice_audit.json",
            mime="application/json",
        )
    with col_right:
        if not df.empty:
            st.download_button(
                "Download as CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name="agent_ice_audit.csv",
                mime="text/csv",
            )

    # --- Detail viewer ---------------------------------------------------
    st.markdown("---")
    st.subheader("Event detail")
    ids = [e.get("event_id") for e in events if e.get("event_id")]
    if not ids:
        return
    selected_id = st.selectbox("Select an event", ids)
    event = next((e for e in events if e.get("event_id") == selected_id), None)
    if event is None:
        return
    st.json(event)