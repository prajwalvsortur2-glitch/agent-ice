"""Render the attack flow diagram used in the Live Monitor and Incident
detail views.

The diagram shows the canonical Agent ICE pipeline:

    USER → AGENT → TOOL REQUEST → ICE → PROVENANCE → RISK → DECISION

Each stage is rendered as a small card. Blocked stages are colored red;
approved stages are colored green. The diagram is purely presentational —
it visualizes a decision the backend already made.
"""
from __future__ import annotations

from typing import Any

import streamlit as st


_STAGE_ORDER = [
    ("USER", "user_intent"),
    ("AGENT", "agent_name"),
    ("TOOL REQUEST", "tool_name"),
    ("ICE", "inspection_id"),
    ("PROVENANCE", "provenance_summary"),
    ("RISK", "risk_summary"),
    ("DECISION", "decision"),
]


def _color_for(decision: str) -> str:
    return {
        "ALLOW": "#16a34a",
        "REVIEW": "#eab308",
        "RESTRICT": "#f97316",
        "BLOCK": "#dc2626",
    }.get(decision, "#64748b")


def render_attack_flow(stage: dict[str, Any]) -> None:
    """Render the vertical pipeline for a single event."""
    decision = stage.get("decision", "BLOCK")
    accent = _color_for(decision)

    for idx, (label, key) in enumerate(_STAGE_ORDER):
        value = stage.get(key, "-")
        is_decision = key == "decision"

        # Color the final decision stage by its decision.
        border = accent if is_decision else "rgba(100,116,139,0.35)"
        background = (
            f"linear-gradient(135deg, {accent}22, {accent}08)"
            if is_decision
            else "rgba(15,23,42,0.03)"
        )
        text_color = accent if is_decision else "#e2e8f0"

        st.markdown(
            f"""
            <div style="
                border:1px solid {border};
                border-radius:10px;
                padding:10px 14px;
                background:{background};
                margin-bottom:4px;
            ">
                <div style="font-size:10px;letter-spacing:1.4px;color:#94a3b8;
                            font-weight:700;">{label}</div>
                <div style="font-size:14px;color:{text_color};font-weight:600;
                            margin-top:2px;word-break:break-word;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if idx < len(_STAGE_ORDER) - 1:
            st.markdown(
                '<div style="text-align:center;color:#64748b;font-size:12px;'
                'margin:-2px 0 2px 0;">▼</div>',
                unsafe_allow_html=True,
            )


def render_compact_flow(decision: str) -> None:
    """Render a compact horizontal flow: USER → AGENT → TOOL → ICE → DECISION."""
    accent = _color_for(decision)
    stages = ["USER", "AGENT", "TOOL", "ICE", "PROVENANCE", "RISK"]
    parts = []
    for s in stages:
        parts.append(
            f'<span style="display:inline-block;padding:4px 10px;margin:2px;'
            f'border-radius:8px;background:rgba(100,116,139,0.15);color:#cbd5e1;'
            f'font-size:11px;font-weight:600;letter-spacing:1px;">{s}</span>'
        )
    parts.append(
        f'<span style="display:inline-block;padding:4px 12px;margin:2px;'
        f'border-radius:8px;background:{accent};color:white;'
        f'font-size:11px;font-weight:700;letter-spacing:1px;">{decision}</span>'
    )
    st.markdown(" ".join(parts), unsafe_allow_html=True)