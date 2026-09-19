"""Policies page: view the loaded policy files."""
from __future__ import annotations

import streamlit as st

from dashboard.utils import backend_reachable, fetch_policies, fetch_tools


def render() -> None:
    st.title("Policies")
    st.caption("Loaded security policy files. Read-only view.")

    if not backend_reachable():
        st.error("Backend is not reachable.")
        return

    result = fetch_policies()
    policies = result.get("policies") or []
    if not policies:
        st.info("No policy files were loaded by the backend.")
    else:
        names = [p.get("name") for p in policies]
        selected = st.selectbox("Policy file", names)
        policy = next(p for p in policies if p.get("name") == selected)

        st.markdown(f"**{policy.get('name')}**")
        content = policy.get("content") or {}
        # Show as formatted YAML-ish JSON view (Streamlit renders JSON nicely).
        st.json(content)
        st.download_button(
            "Download as JSON",
            data=__import__("json").dumps(content, indent=2, default=str),
            file_name=selected.replace(".yaml", ".json"),
            mime="application/json",
        )

    st.markdown("---")
    st.subheader("Registered tools")
    tools = fetch_tools().get("tools") or []
    if not tools:
        st.info("The backend did not report any registered tools.")
        return

    for tool in tools:
        with st.expander(f"`{tool.get('name')}` — {tool.get('description','')}"):
            st.markdown("**Argument schema**")
            st.json(tool.get("arguments_schema") or {})