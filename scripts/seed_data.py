"""Seed the Agent ICE database with fixtures.

Creates:
  * a demo session with the canonical "Summarize my unread emails" intent
  * the email/fixture files are already on disk and read by the tools
  * a small benign history so the UI has something to render on first load

Safe to run repeatedly: the reset step wipes only Agent ICE tables, never
fixture files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is importable when invoked as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ice.intent_anchor import IntentAnchorService  # noqa: E402
from app.models import ProvenanceRef, ToolCall, TrustLevel  # noqa: E402
from app.storage.audit_repository import AuditRepository  # noqa: E402
from app.storage.database import init_db  # noqa: E402


DEFAULT_INTENT = "Summarize my unread emails."


def seed(wipe: bool) -> None:
    init_db()
    repo = AuditRepository()

    if wipe:
        repo.wipe_all()
        print("Wiped existing Agent ICE tables.")

    anchor_svc = IntentAnchorService()
    anchor, intent_hash = anchor_svc.bootstrap(DEFAULT_INTENT)

    session_id = "demo-session"
    existing = repo.get_session(session_id)
    if existing is not None:
        print(f"Demo session {session_id!r} already exists; skipping creation.")
    else:
        repo.create_session(
            session_id=session_id,
            agent_name="qwen-agent",
            intent=anchor,
            intent_hash=intent_hash,
        )
        print(f"Created demo session {session_id!r}.")

        # Seed a couple of benign audit rows so the UI renders something.
        for tool, args in (
            ("read_email", {"id": "email_001"}),
            ("read_email", {"id": "email_002"}),
        ):
            repo.record_tool_request(
                session_id=session_id,
                tool_call=ToolCall(
                    tool_name=tool,
                    arguments=args,
                    provenance=[
                        ProvenanceRef(
                            source_id="user_prompt",
                            source_type="user_prompt",
                            trust_level=TrustLevel.TRUSTED,
                        )
                    ],
                ),
            )
            repo.record_audit_event(
                session_id=session_id,
                event_type="inspect",
                tool_name=tool,
                decision=None,
                reason_codes=["SEEDED"],
                detail={"seeded": True, "arguments": args},
            )

    stats = repo.stats()
    print("Row counts:")
    for key, value in stats.items():
        print(f"  {key:<22} {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Agent ICE fixtures.")
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Wipe all Agent ICE tables before seeding.",
    )
    args = parser.parse_args()
    seed(wipe=args.wipe)
    print("Seed complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())