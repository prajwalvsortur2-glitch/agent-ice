"""Reset the entire Agent ICE demo state.

  * wipes all Agent ICE DB rows
  * recreates the schema
  * clears the in-memory outboxes and record store
  * reseeds the demo session

The fixture files under data/fixtures/ are NOT touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dependencies import reset_dependency_caches  # noqa: E402
from app.storage.audit_repository import AuditRepository  # noqa: E402
from app.storage.database import drop_db, init_db  # noqa: E402


def reset_all() -> None:
    print("Resetting Agent ICE state...")
    reset_dependency_caches()

    drop_db()
    init_db()
    print("  database schema recreated")

    repo = AuditRepository()
    repo.wipe_all()
    print("  audit tables wiped")

    # Clear tool-side state.
    from app.tools.communication_tool import SendEmailTool
    from app.tools.record_tool import DeleteRecordTool

    SendEmailTool.clear_outbox()
    DeleteRecordTool.reset()
    print("  tool state cleared")

    # Reseed the demo session.
    from scripts.seed_data import seed

    seed(wipe=False)
    print("Reset complete.")


def main() -> int:
    reset_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())