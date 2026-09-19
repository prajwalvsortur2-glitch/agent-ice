"""Evaluation page: run the built-in evaluator and render the results.

The numbers shown here are produced by actually running
`scripts/evaluate.py`. Nothing is hard-coded.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.utils import backend_base_url


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_evaluate() -> tuple[int, str, dict | None]:
    root = _project_root()
    script = root / "scripts" / "evaluate.py"
    out_path = root / "data" / "results" / "dashboard_eval.json"

    cmd = [sys.executable, str(script), "--json", str(out_path)]
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=600,
    )

    payload = None
    if out_path.exists():
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None

    return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or ""), payload


def _run_benchmark(runs: int) -> tuple[int, str, dict | None]:
    root = _project_root()
    script = root / "scripts" / "benchmark.py"
    out_path = root / "data" / "results" / "dashboard_bench.json"

    cmd = [sys.executable, str(script), "--runs", str(runs), "--json", str(out_path)]
    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=900,
    )

    payload = None
    if out_path.exists():
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None

    return proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or ""), payload


def render() -> None:
    st.title("Evaluation")
    st.caption(
        "Every metric on this page is produced by executing the local "
        "evaluator against the attack and benign datasets. Nothing is "
        "hard-coded."
    )

    st.markdown(f"**Backend base URL:** `{backend_base_url()}`")

    st.markdown("---")
    st.subheader("Run evaluation")
    st.caption(
        "Runs the full 43-attack + 12-benign sweep. Ollama may be unavailable; "
        "high-risk requests will fail closed."
    )
    if st.button("Run evaluation", type="primary"):
        with st.spinner("Running evaluation..."):
            code, output, payload = _run_evaluate()
        st.session_state["eval_payload"] = payload
        st.session_state["eval_output"] = output
        st.session_state["eval_code"] = code

    payload = st.session_state.get("eval_payload")
    if payload is None:
        st.info("Click **Run evaluation** to generate the report.")
    else:
        summary = payload.get("summary") or {}
        results = payload.get("results") or {}

        st.markdown("### Attack cases")
        atk_total = summary.get("attack_total", 0)
        atk_decisions = summary.get("attack_decisions") or {}
        cols = st.columns(5)
        cols[0].metric("Total", atk_total)
        cols[1].metric("Blocked", atk_decisions.get("BLOCK", 0))
        cols[2].metric("Reviewed", atk_decisions.get("REVIEW", 0))
        cols[3].metric("Restricted", atk_decisions.get("RESTRICT", 0))
        cols[4].metric("Allowed", atk_decisions.get("ALLOW", 0))

        # Per-category breakdown.
        rows = []
        for r in results.get("attack_results", []):
            rows.append(
                {
                    "case_id": r.get("case_id"),
                    "decision": r.get("decision"),
                    "risk_level": r.get("risk_level"),
                    "risk_score": r.get("risk_score"),
                    "latency_ms": round(r.get("latency_ms", 0), 2),
                }
            )
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### Benign cases")
        ben_total = summary.get("benign_total", 0)
        ben_decisions = summary.get("benign_decisions") or {}
        cols = st.columns(4)
        cols[0].metric("Total", ben_total)
        cols[1].metric("Allowed", ben_decisions.get("ALLOW", 0))
        cols[2].metric("Reviewed", ben_decisions.get("REVIEW", 0))
        cols[3].metric("Blocked", ben_decisions.get("BLOCK", 0))

        st.markdown("### Latency")
        lat = summary.get("latency_all") or {}
        cols = st.columns(5)
        cols[0].metric("Mean", f"{lat.get('mean', 0)} ms")
        cols[1].metric("Median", f"{lat.get('median', 0)} ms")
        cols[2].metric("P95", f"{lat.get('p95', 0)} ms")
        cols[3].metric("Min", f"{lat.get('min', 0)} ms")
        cols[4].metric("Max", f"{lat.get('max', 0)} ms")

        st.markdown("### False positives / negatives")
        st.markdown(f"- False positives: `{len(summary.get('false_positives') or [])}`")
        st.markdown(f"- False negatives: `{len(summary.get('false_negatives') or [])}`")
        if summary.get("false_negatives"):
            st.error("Some attack cases were allowed: " + ", ".join(summary["false_negatives"]))

        with st.expander("Raw evaluation output"):
            st.code(st.session_state.get("eval_output") or "", language="text")

    st.markdown("---")
    st.subheader("Run benchmark")
    runs = st.slider("Runs per payload", min_value=5, max_value=100, value=25, step=5)
    if st.button("Run benchmark"):
        with st.spinner("Running benchmark..."):
            code, output, payload = _run_benchmark(runs)
        st.session_state["bench_payload"] = payload
        st.session_state["bench_output"] = output

    bench = st.session_state.get("bench_payload")
    if bench is None:
        st.info("Click **Run benchmark** to measure fast-path and deep-path latency.")
    else:
        stats = bench.get("stats") or []
        if stats:
            df = pd.DataFrame(stats)
            # Rename for display.
            df = df.rename(
                columns={
                    "name": "payload",
                    "runs": "runs",
                    "mean_ms": "mean (ms)",
                    "median_ms": "median (ms)",
                    "p95_ms": "p95 (ms)",
                    "min_ms": "min (ms)",
                    "max_ms": "max (ms)",
                }
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("Raw benchmark output"):
            st.code(st.session_state.get("bench_output") or "", language="text")