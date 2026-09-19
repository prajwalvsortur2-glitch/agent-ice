"""Render a single security decision as a styled card."""
from __future__ import annotations

from typing import Any

import streamlit as st

from dashboard.utils import DECISION_META, decision_label, risk_label


def render_decision_card(
    *,
    decision: str,
    risk_score: int,
    risk_level: str,
    explanation: str,
    reason_codes: list[str],
    tool_name: str,
    resource: str | None = None,
    capability: str | None = None,
) -> None:
    meta = DECISION_META.get(decision, {"emoji": "⚪", "color": "#64748b"})
    color = meta["color"]

    st.markdown(
        f"""
        <div style="
            border: 2px solid {color};
            border-radius: 12px;
            padding: 20px 22px;
            background: linear-gradient(135deg, rgba(15,23,42,0.06), rgba(15,23,42,0.02));
            margin-bottom: 8px;
        ">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:12px;letter-spacing:1.5px;color:#64748b;font-weight:600;">DECISION</div>
                    <div style="font-size:28px;font-weight:800;color:{color};margin-top:2px;">
                        {decision_label(decision)}
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px;letter-spacing:1.5px;color:#64748b;font-weight:600;">RISK</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;">
                        {risk_label(risk_level)} <span style="color:#94a3b8;">· {risk_score}/100</span>
                    </div>
                </div>
            </div>
            <hr style="border:none;border-top:1px solid rgba(100,116,139,0.25);margin:14px 0 10px 0;">
            <div style="font-size:14px;color:#cbd5e1;">
                <div><b>Tool:</b> <code>{tool_name}</code></div>
                {f'<div><b>Resource:</b> <code>{resource}</code></div>' if resource else ''}
                {f'<div><b>Capability:</b> <code>{capability}</code></div>' if capability else ''}
            </div>
            <div style="margin-top:12px;font-size:14px;color:#e2e8f0;">{explanation or '-'}</div>
            {f'<div style="margin-top:10px;font-size:12px;color:#94a3b8;">Reason codes: {", ".join(reason_codes)}</div>' if reason_codes else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_pill(decision: str) -> str:
    """Return an inline HTML pill (use with st.markdown unsafe_allow_html)."""
    meta = DECISION_META.get(decision, {"emoji": "⚪", "color": "#64748b"})
    return (
        f'<span style="background:{meta["color"]};color:white;padding:2px 10px;'
        f'border-radius:999px;font-size:12px;font-weight:700;">'
        f'{meta["emoji"]} {decision}</span>'
    )


def render_reason_codes(codes: list[str]) -> None:
    if not codes:
        st.caption("No reason codes recorded.")
        return
    for code in codes:
        st.markdown(f"- `{code}`")


def render_provenance_badges(provenance: list[dict[str, Any]]) -> None:
    if not provenance:
        st.caption("No provenance recorded.")
        return
    for ref in provenance:
        trust = ref.get("trust_level", "UNKNOWN")
        color = {
            "TRUSTED": "#16a34a",
            "RESTRICTED": "#eab308",
            "UNTRUSTED": "#dc2626",
        }.get(trust, "#64748b")
        st.markdown(
            f'<span style="background:{color};color:white;padding:2px 10px;'
            f'border-radius:999px;font-size:12px;font-weight:600;margin-right:6px;">'
            f'{trust}</span>'
            f'<span style="font-size:13px;color:#cbd5e1;">'
            f'{ref.get("source_type","?")} · <code>{ref.get("source_id","?")}</code></span>',
            unsafe_allow_html=True,
        )