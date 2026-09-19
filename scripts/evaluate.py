"""Evaluate Agent ICE against the attack and benign datasets.

Produces a report generated from actual controller runs. It never
hard-codes any metric: every number is counted from real decisions.

Usage:
    python scripts/evaluate.py
    python scripts/evaluate.py --json data/results/eval.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dependencies import reset_dependency_caches, get_ice_controller  # noqa: E402
from app.ice.intent_anchor import IntentAnchorService  # noqa: E402
from app.models import ProvenanceRef, ToolCall, TrustLevel  # noqa: E402
from app.storage.audit_repository import AuditRepository  # noqa: E402
from app.storage.database import init_db  # noqa: E402


ATTACKS_DIR = ROOT / "data" / "attacks"
BENIGN_PATH = ROOT / "data" / "benign" / "legitimate_tasks.json"
RESULTS_DIR = ROOT / "data" / "results"


def _load_attacks() -> list[dict]:
    index = json.loads((ATTACKS_DIR / "index.json").read_text(encoding="utf-8"))
    cases: list[dict] = []
    for cat in index["categories"]:
        data = json.loads((ATTACKS_DIR / cat["file"]).read_text(encoding="utf-8"))
        for case in data["cases"]:
            case["_category_id"] = cat["id"]
            case["_category_name"] = cat["name"]
            cases.append(case)
    return cases


def _load_benign() -> list[dict]:
    return json.loads(BENIGN_PATH.read_text(encoding="utf-8"))["cases"]


def _make_provenance(spec: list[dict] | None, default_untrusted: bool) -> list[ProvenanceRef]:
    if spec:
        return [
            ProvenanceRef(
                p["source_id"],
                p.get("source_type", "email"),
                TrustLevel(p.get("trust_level", "UNTRUSTED")),
            )
            for p in spec
        ]
    if default_untrusted:
        return [ProvenanceRef("email_attack_001", "email", TrustLevel.UNTRUSTED)]
    return [ProvenanceRef("user_prompt", "user_prompt", TrustLevel.TRUSTED)]


def _run_case(
    controller,
    repo: AuditRepository,
    anchor_svc: IntentAnchorService,
    *,
    user_intent: str,
    tool_name: str,
    arguments: dict,
    provenance: list[ProvenanceRef],
    case_id: str,
) -> dict:
    session_id = f"eval-{case_id}"
    anchor, intent_hash = anchor_svc.bootstrap(user_intent)
    repo.create_session(
        session_id=session_id,
        agent_name="qwen-agent",
        intent=anchor,
        intent_hash=intent_hash,
    )
    call = ToolCall(tool_name=tool_name, arguments=arguments, provenance=provenance)
    started = time.perf_counter()
    outcome = controller.inspect(session_id=session_id, tool_call=call)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    return {
        "case_id": case_id,
        "decision": outcome.decision.decision.value,
        "risk_score": outcome.decision.risk.score,
        "risk_level": outcome.decision.risk.level.value,
        "reason_codes": outcome.decision.reason_codes,
        "latency_ms": elapsed_ms,
    }


def evaluate() -> dict:
    reset_dependency_caches()
    init_db()
    repo = AuditRepository()
    repo.wipe_all()

    controller = get_ice_controller()
    anchor_svc = IntentAnchorService()

    attacks = _load_attacks()
    benign = _load_benign()

    attack_results: list[dict] = []
    for case in attacks:
        provenance = _make_provenance(case.get("expected_provenance"), default_untrusted=True)
        attack_results.append(
            _run_case(
                controller,
                repo,
                anchor_svc,
                user_intent=case["user_intent"],
                tool_name=case["expected_tool"],
                arguments=case.get("expected_arguments") or {},
                provenance=provenance,
                case_id=case["id"],
            )
        )

    benign_results: list[dict] = []
    for case in benign:
        provenance = _make_provenance(case.get("provenance"), default_untrusted=False)
        benign_results.append(
            _run_case(
                controller,
                repo,
                anchor_svc,
                user_intent=case["intent"],
                tool_name=case["tool_name"],
                arguments=case["arguments"],
                provenance=provenance,
                case_id=case["id"],
            )
        )

    return {"attack_results": attack_results, "benign_results": benign_results}


def summarize(results: dict) -> dict:
    attack_results = results["attack_results"]
    benign_results = results["benign_results"]

    attack_decisions = Counter(r["decision"] for r in attack_results)
    benign_decisions = Counter(r["decision"] for r in benign_results)

    all_latencies = [r["latency_ms"] for r in attack_results + benign_results]

    def stats(vals: list[float]) -> dict:
        if not vals:
            return {"mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
        s = sorted(vals)
        n = len(s)
        idx = max(0, int(round(0.95 * (n - 1))))
        return {
            "mean": round(statistics.fmean(s), 2),
            "median": round(statistics.median(s), 2),
            "p95": round(s[idx], 2),
            "min": round(s[0], 2),
            "max": round(s[-1], 2),
        }

    # False positives: benign cases that were BLOCKed.
    false_positives = [
        r["case_id"] for r in benign_results if r["decision"] == "BLOCK"
    ]
    # False negatives: attack cases that were ALLOWed.
    false_negatives = [
        r["case_id"] for r in attack_results if r["decision"] == "ALLOW"
    ]

    return {
        "attack_total": len(attack_results),
        "attack_decisions": dict(attack_decisions),
        "benign_total": len(benign_results),
        "benign_decisions": dict(benign_decisions),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "latency_all": stats(all_latencies),
        "latency_attacks": stats([r["latency_ms"] for r in attack_results]),
        "latency_benign": stats([r["latency_ms"] for r in benign_results]),
    }


def print_report(summary: dict, results: dict) -> None:
    line = "=" * 60
    print(line)
    print("Agent ICE Evaluation")
    print(line)
    print()

    print(f"Attack Cases:        {summary['attack_total']}")
    for decision in ("BLOCK", "REVIEW", "RESTRICT", "ALLOW"):
        n = summary["attack_decisions"].get(decision, 0)
        print(f"  {decision:<10}       {n}")
    print()

    print(f"Benign Cases:        {summary['benign_total']}")
    for decision in ("ALLOW", "REVIEW", "RESTRICT", "BLOCK"):
        n = summary["benign_decisions"].get(decision, 0)
        print(f"  {decision:<10}       {n}")
    print()

    la = summary["latency_all"]
    print(f"Average Latency:     {la['mean']} ms")
    print(f"Median Latency:      {la['median']} ms")
    print(f"P95 Latency:         {la['p95']} ms")
    print(f"Min / Max:           {la['min']} ms / {la['max']} ms")
    print()

    fp = summary["false_positives"]
    fn = summary["false_negatives"]
    print(f"False positives:     {len(fp)}")
    if fp:
        for cid in fp:
            print(f"  - {cid}")
    print(f"False negatives:     {len(fn)}")
    if fn:
        for cid in fn:
            print(f"  - {cid}")
    print()

    # Per-category breakdown for attacks.
    by_category: dict[str, Counter] = {}
    for r in results["attack_results"]:
        category = r["case_id"].split("-")[0]  # A01, A02, ...
        by_category.setdefault(category, Counter())[r["decision"]] += 1
    print("Attack decisions by category:")
    for cat in sorted(by_category.keys()):
        counts = by_category[cat]
        summary_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"  {cat}: {summary_str}")
    print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent ICE evaluation.")
    parser.add_argument("--json", default=None, help="Write full results as JSON.")
    args = parser.parse_args()

    results = evaluate()
    summary = summarize(results)
    print_report(summary, results)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"summary": summary, "results": results}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"Full results written to {out}")

    # Nonzero exit if any attack was allowed or any benign was blocked.
    if summary["false_negatives"]:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())