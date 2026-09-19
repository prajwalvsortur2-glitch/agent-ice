"""Render a risk gauge card."""
from __future__ import annotations

import streamlit as st


_RISK_COLORS = {
    "LOW": "#16a34a",
    "MEDIUM": "#eab308",
    "HIGH": "#f97316",
    "CRITICAL": "#dc2626",
}


def render_risk_gauge(score: int, level: str, title: str = "Risk Score") -> None:
    color = _RISK_COLORS.get(level, "#64748b")
    pct = max(0, min(100, int(score)))
    st.markdown(
        f"""
        <div style="border:1px solid rgba(100,116,139,0.35);border-radius:12px;
                    padding:14px 16px;background:rgba(15,23,42,0.04);">
            <div style="display:flex;justify-content:space-between;align-items:baseline;">
                <div style="font-size:12px;letter-spacing:1.4px;color:#64748b;font-weight:600;">
                    {title.upper()}
                </div>
                <div style="font-size:22px;font-weight:800;color:{color};">{pct}</div>
            </div>
            <div style="height:8px;border-radius:6px;background:rgba(100,116,139,0.25);
                        margin-top:8px;overflow:hidden;">
                <div style="height:100%;width:{pct}%;background:{color};"></div>
            </div>
            <div style="margin-top:6px;font-size:12px;color:{color};font-weight:700;
                        letter-spacing:1.2px;">{level}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_breakdown(signals: dict[str, int]) -> None:
    if not signals:
        st.caption("No risk signals recorded.")
        return
    for name, weight in sorted(signals.items(), key=lambda kv: -kv[1]):
        st.markdown(f"- `{name}` → **+{weight}**")