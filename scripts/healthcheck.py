"""Health check for the Agent ICE backend and its dependencies.

Exit codes:
  0  backend + DB reachable, Ollama reachable and model installed
  1  backend unreachable
  2  DB not writable
  3  Ollama unreachable or model missing (non-fatal for the core pipeline,
     but reported as a warning)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402


def check_backend(base_url: str, timeout: float) -> tuple[int, dict]:
    try:
        resp = httpx.get(f"{base_url}/health", timeout=timeout)
        resp.raise_for_status()
        return 0, resp.json()
    except httpx.HTTPError as exc:
        return 1, {"error": f"backend unreachable: {exc}"}


def check_database() -> tuple[int, dict]:
    try:
        from app.storage.audit_repository import AuditRepository
        from app.storage.database import init_db

        init_db()
        stats = AuditRepository().stats()
        return 0, {"stats": stats}
    except Exception as exc:  # noqa: BLE001
        return 2, {"error": f"database not writable: {exc}"}


def check_ollama(base_url: str, model: str, timeout: float) -> tuple[int, dict]:
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        return 3, {"reachable": False, "error": str(exc)}

    names = [m.get("name", "") for m in data.get("models", [])]
    installed = any(n == model or n.startswith(model + ":") for n in names)
    return (0 if installed else 3), {
        "reachable": True,
        "model": model,
        "model_available": installed,
        "available_models": names,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent ICE health check.")
    parser.add_argument("--base-url", default=None, help="Backend base URL.")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    settings = get_settings()
    base_url = args.base_url or f"http://{settings.api_host}:{settings.api_port}"

    backend_code, backend = check_backend(base_url, args.timeout)
    db_code, db = check_database()
    ollama_code, ollama = check_ollama(
        settings.ollama_base_url, settings.ollama_model, args.timeout
    )

    report = {
        "backend": {"code": backend_code, "detail": backend},
        "database": {"code": db_code, "detail": db},
        "ollama": {"code": ollama_code, "detail": ollama},
    }

    if args.json:
        print(json.dumps(report, default=str, indent=2))
    else:
        def line(name: str, code: int, detail) -> None:
            marker = "OK" if code == 0 else f"FAIL({code})"
            print(f"[{marker:<8}] {name:<10} {detail}")

        line("backend", backend_code, backend if backend_code else "reachable")
        line("database", db_code, db if db_code else f"rows={sum(db['stats'].values())}")
        if ollama_code == 0:
            line("ollama", 0, f"reachable, model {settings.ollama_model!r} installed")
        else:
            line("ollama", ollama_code, ollama)

    # Backend or DB failure is fatal; Ollama failure is a warning only.
    if backend_code != 0:
        return 1
    if db_code != 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())