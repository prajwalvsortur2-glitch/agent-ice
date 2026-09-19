"""Incidents page: every blocked or restricted action, with reasons."""
from __future__ import annotations

import streamlit as st

from dashboard.components.attack_flow import render_attack_flow
from dashboard.components.decision_card import (
    render_decision_card,
    render_provenance_badges,
    render_reason_codes,
)
from dashboard.components.event_table import render_incident_table
from dashboard.components.provenance_graph import render_provenance_graph
from dashboard.components.risk_card import render_risk_gauge
from dashboard.utils import (
    backend_reachable,
    fetch_incidents,
    fmt_ts,
    incidents_to_dataframe,
)


def render() -> None:
    st.title("Incidents")
    st.caption("Every non-allow decision, with the evidence that produced it.")

    if not backend_reachable():
        st.error("Backend is not reachable.")
        return

    # --- Filters ---------------------------------------------------------
    col_a, col_b, col_c, col_d = st.columns([2, 2, 2, 1])
    with col_a:
        risk_filter = st.selectbox(
            "Risk level", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"], index=0
        )
    with col_b:
        decision_filter = st.selectbox(
            "Decision", ["All", "BLOCK", "RESTRICT", "REVIEW"], index=0
        )
    with col_c:
        session_filter = st.text_input("Session id contains", value="")
    with col_d:
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=200, step=10)

    params: dict = {"limit": int(limit)}
    if risk_filter != "All":
        params["risk_level"] = risk_filter
    if decision_filter != "All":
        params["decision"] = decision_filter

    result = fetch_incidents(**params)
    incidents = result.get("incidents") or []
    if session_filter:
        incidents = [
            i for i in incidents if session_filter.lower() in (i.get("session_id") or "").lower()
        ]

    total = len(incidents)

    if total == 0:
        st.info("No incidents match the current filters.")
        return

    st.markdown(f"**{total} incident(s)**")

    df = incidents_to_dataframe(incidents)
    render_incident_table(df)

    st.markdown("---")
    st.subheader("Incident detail")

    # Select by incident id.
    ids = [i.get("incident_id") for i in incidents if i.get("incident_id")]
    selected_id = st.selectbox("Select an incident", ids)
    incident = next((i for i in incidents if i.get("incident_id") == selected_id), None)
    if incident is None:
        return

    left, right = st.columns([2, 1])

    with left:
        render_decision_card(
            decision=incident.get("decision", "-"),
            risk_score=incident.get("risk_score", 0),
            risk_level=incident.get("risk_level", "-"),
            explanation=incident.get("explanation", ""),
            reason_codes=incident.get("reason_codes") or [],
            tool_name=incident.get("tool_name", "-"),
        )

        st.markdown("#### Why was this blocked?")
        st.markdown(incident.get("explanation") or "_No explanation recorded._")

        st.markdown("#### Triggered reason codes")
        render_reason_codes(incident.get("reason_codes") or [])

        st.markdown("#### Provenance")
        render_provenance_badges(incident.get("provenance") or [])

        st.markdown("#### Tool arguments (redacted at source)")
        st.json(incident.get("tool_arguments") or {})

        if incident.get("containment"):
            st.markdown("#### Containment")
            st.json(incident["containment"])

    with right:
        render_risk_gauge(incident.get("risk_score", 0), incident.get("risk_level", "-"))
        st.markdown("")
        st.markdown(f"**Incident id:** `{incident.get('incident_id')}`")
        st.markdown(f"**Session:** `{incident.get('session_id')}`")
        st.markdown(f"**Created:** {fmt_ts(incident.get('created_at'))}")
        st.markdown(f"**User intent:** {incident.get('user_intent')}")

    st.markdown("---")
    st.subheader("Provenance graph")
    render_provenance_graph(
        sources=incident.get("provenance") or [],
        tool_name=incident.get("tool_name", "-"),
        decision=incident.get("decision", "-"),
        resource=(incident.get("tool_arguments") or {}).get("table")
        or (incident.get("tool_arguments") or {}).get("path")
        or (incident.get("tool_arguments") or {}).get("to"),
    )

    st.markdown("---")
    st.subheader("Attack flow")
    render_attack_flow(
        {
            "user_intent": incident.get("user_intent", "-"),
            "agent_name": "qwen-agent",
            "tool_name": incident.get("tool_name", "-"),
            "inspection_id": "-",
            "provenance_summary": ", ".join(
                f"{p.get('trust_level','?')}:{p.get('source_id','?')}"
                for p in (incident.get("provenance") or [])
            ) or "no provenance",
            "risk_summary": f"{incident.get('risk_level','-')} · {incident.get('risk_score','-')}/100",
            "decision": incident.get("decision", "-"),
        }
    )