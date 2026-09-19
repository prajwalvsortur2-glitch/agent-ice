"""Render an audit or incident table with consistent styling."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def render_audit_table(df: pd.DataFrame, *, height: int = 420) -> None:
    if df.empty:
        st.info("No events match the current filters.")
        return
    st.dataframe(
        df,
        use_container_width=True,
        height=height,
        hide_index=True,
    )


def render_incident_table(df: pd.DataFrame, *, height: int = 420) -> None:
    if df.empty:
        st.info("No incidents match the current filters.")
        return
    st.dataframe(
        df,
        use_container_width=True,
        height=height,
        hide_index=True,
    )


def render_kpi_row(kpis: dict[str, int]) -> None:
    cols = st.columns(len(kpis))
    for col, (label, value) in zip(cols, kpis.items()):
        with col:
            st.metric(label=label, value=int(value))


def render_status_row(items: dict[str, str]) -> None:
    cols = st.columns(len(items))
    for col, (label, state) in zip(cols, items.items()):
        color = {
            "HEALTHY": "#16a34a",
            "ACTIVE": "#16a34a",
            "READY": "#16a34a",
            "UNREACHABLE": "#dc2626",
            "MODEL_MISSING": "#eab308",
            "UNHEALTHY": "#dc2626",
            "DEGRADED": "#eab308",
            "UNKNOWN": "#64748b",
        }.get(state, "#64748b")
        with col:
            st.markdown(
                f"""
                <div style="border:1px solid rgba(100,116,139,0.35);border-radius:10px;
                            padding:12px 14px;background:rgba(15,23,42,0.03);">
                    <div style="font-size:11px;letter-spacing:1.4px;color:#64748b;
                                font-weight:600;">{label.upper()}</div>
                    <div style="font-size:15px;font-weight:700;color:{color};
                                margin-top:4px;">● {state}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )