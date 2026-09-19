"""Agent ICE — analyst dashboard (Streamlit).

Read-only. This application never makes security decisions: it renders
data the trusted Agent ICE backend has already recorded.

Run with:
    streamlit run dashboard/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make the project root importable when run as `streamlit run dashboard/app.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.utils import backend_base_url, fetch_health  # noqa: E402


PAGES = {
    "Overview":     ("dashboard.pages.overview", "render"),
    "Live Monitor": ("dashboard.pages.live_monitor", "render"),
    "Incidents":    ("dashboard.pages.incidents", "render"),
    "Audit Logs":   ("dashboard.pages.audit_logs", "render"),
    "Policies":     ("dashboard.pages.policies", "render"),
    "Evaluation":   ("dashboard.pages.evaluation", "render"),
}


def _load_renderer(module_path: str, attr: str):
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, attr)


def main() -> None:
    st.set_page_config(
        page_title="Agent ICE — Analyst Console",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Minimal global styling to make it feel like a security console.
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        h1, h2, h3 { letter-spacing: 0.2px; }
        code { color: #93c5fd; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("## 🛡️ Agent ICE")
        st.caption("Intent-to-Action Security Controller")
        st.markdown("---")

        page = st.radio(
            "Section",
            list(PAGES.keys()),
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption("Backend")
        st.code(backend_base_url(), language="text")
        health = fetch_health()
        if "_error" in health:
            st.error("Unreachable")
        else:
            st.success(
                f"API healthy · env `{health.get('app_env','?')}` · v{health.get('version','?')}"
            )

        st.markdown("---")
        if st.button("Clear cache"):
            st.cache_data.clear()
            st.rerun()

        st.caption(
            "This dashboard is read-only. It never issues decisions and never "
            "holds signing secrets."
        )

    module_path, attr = PAGES[page]
    render = _load_renderer(module_path, attr)
    render()


if __name__ == "__main__":
    main()