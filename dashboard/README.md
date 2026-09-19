# Agent ICE — Analyst Dashboard

A read-only Streamlit console for analysts and developers. It renders
what the trusted Agent ICE backend has recorded. It does not make
security decisions and never holds signing secrets.

## What it shows

- **Overview** — component health (API, DB, Ollama, Qwen, ICE) and live
  counters for ALLOW / REVIEW / RESTRICT / BLOCK taken from real events.
- **Live Monitor** — the most recent decisions, each rendered as a
  compact flow, with an expandable full attack-flow diagram.
- **Incidents** — every blocked, restricted or reviewed action with a
  "Why was this blocked?" explanation, reason codes, provenance and a
  Plotly provenance graph.
- **Audit Logs** — search, filter, download as JSON or CSV.
- **Policies** — the currently-loaded policy files, and the tool
  registry reported by the backend.
- **Evaluation** — runs `scripts/evaluate.py` and `scripts/benchmark.py`
  in a subprocess and displays their actual output. No metric is
  hard-coded.

## Requirements

The dashboard requires the backend to be reachable. It talks to it over
HTTP at `AGENT_ICE_BACKEND` (default `http://127.0.0.1:8000`).

## Setup (Windows 11)

```powershell
cd agent-ice
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r dashboard\requirements.txt