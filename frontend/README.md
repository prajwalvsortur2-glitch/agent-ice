# Agent ICE — Frontend

React + TypeScript + Vite + Tailwind security console for Agent ICE.

## The one rule

**The frontend is never the authority.**

Every decision — `ALLOW`, `REVIEW`, `RESTRICT`, `BLOCK` — comes from the
backend. The UI displays decisions. The UI does not make them. No secret is
stored in this codebase.

Receipt verification happens server-side by the executor. The UI can *show*
a receipt; it never trusts one.

## Requirements

- Node.js 20+
- A running Agent ICE backend at `http://127.0.0.1:8000` (see `../README.md`)

## Setup

```powershell
cd frontend
Copy-Item .env.example .env
npm install