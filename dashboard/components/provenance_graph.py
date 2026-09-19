"""Provenance visualization.

Uses Plotly to draw a left-to-right trust graph:
    source → tool call → ICE → decision

Each node is colored by trust level. Edges carry the trust level as a
label. This is a visualization of *recorded* provenance — it does not
perform any analysis.
"""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st


_TRUST_COLORS = {
    "TRUSTED": "#16a34a",
    "RESTRICTED": "#eab308",
    "UNTRUSTED": "#dc2626",
    "SYSTEM": "#3b82f6",
    "DECISION_ALLOW": "#16a34a",
    "DECISION_REVIEW": "#eab308",
    "DECISION_RESTRICT": "#f97316",
    "DECISION_BLOCK": "#dc2626",
}


def render_provenance_graph(
    *,
    sources: list[dict[str, Any]],
    tool_name: str,
    decision: str,
    resource: str | None = None,
) -> None:
    """Render a horizontal trust graph for a single decision."""
    if not sources:
        st.info("No provenance information available for this decision.")
        return

    # Node layout: sources on the left, tool in the middle, decision on the right.
    xs: list[float] = []
    ys: list[float] = []
    labels: list[str] = []
    colors: list[str] = []
    hover: list[str] = []

    n = len(sources)
    for idx, src in enumerate(sources):
        y = 1.0 - (idx / max(1, n - 1)) if n > 1 else 0.5
        xs.append(0.0)
        ys.append(y)
        labels.append(f"{src.get('source_type','?')}\n{src.get('source_id','?')}")
        colors.append(_TRUST_COLORS.get(src.get("trust_level", "UNTRUSTED"), "#64748b"))
        hover.append(
            f"source_id: {src.get('source_id')}<br>"
            f"source_type: {src.get('source_type')}<br>"
            f"trust_level: {src.get('trust_level')}"
        )

    xs.append(1.0)
    ys.append(0.5)
    labels.append(f"TOOL\n{tool_name}")
    colors.append(_TRUST_COLORS["SYSTEM"])
    hover.append(f"tool: {tool_name}<br>resource: {resource or '-'}")

    xs.append(2.0)
    ys.append(0.5)
    labels.append(f"ICE\n{decision}")
    colors.append(_TRUST_COLORS.get(f"DECISION_{decision}", "#64748b"))
    hover.append(f"decision: {decision}")

    # Edges from each source to the tool, then tool to ICE.
    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    edge_colors: list[str] = []

    for idx in range(n):
        y = ys[idx]
        edge_x.extend([0.0, 1.0, None])
        edge_y.extend([y, 0.5, None])
        edge_colors.append(colors[idx])

    edge_x.extend([1.0, 2.0, None])
    edge_y.extend([0.5, 0.5, None])

    fig = go.Figure()

    # Edges
    for idx in range(n):
        fig.add_trace(
            go.Scatter(
                x=[0.0, 1.0],
                y=[ys[idx], 0.5],
                mode="lines",
                line=dict(color=colors[idx], width=2),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[1.0, 2.0],
            y=[0.5, 0.5],
            mode="lines",
            line=dict(color="#64748b", width=2, dash="dot"),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Nodes
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            marker=dict(size=34, color=colors, line=dict(color="#0f172a", width=2)),
            text=labels,
            textposition="bottom center",
            textfont=dict(size=11, color="#e2e8f0"),
            hovertext=hover,
            hoverinfo="text",
            showlegend=False,
        )
    )

    fig.update_layout(
        height=340,
        margin=dict(l=10, r=10, t=10, b=30),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False, range=[-0.3, 2.3]),
        yaxis=dict(visible=False, range=[-0.2, 1.2]),
    )

    st.plotly_chart(fig, use_container_width=True)