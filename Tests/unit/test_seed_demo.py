from app.storage.audit_repository import AuditRepository
from scripts.seed_demo import seed_demo


def test_seed_demo_populates_real_database() -> None:
    repo = AuditRepository()
    repo.wipe_all()

    seed_demo(reset=False)
    stats = repo.stats()

    assert stats["sessions"] >= 20
    assert stats["tool_requests"] >= 100
    assert stats["audit_events"] >= 100
    assert stats["incidents"] >= 10
    assert stats["provenance_events"] >= 30

    seed_demo(reset=True)
    stats = repo.stats()
    assert stats["sessions"] >= 20
    assert stats["audit_events"] >= 100
