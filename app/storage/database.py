"""Database engine, session factory, and initialization helpers."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url

    if url.startswith("sqlite:///"):
        db_path_str = url.replace("sqlite:///", "", 1)
        db_path = Path(db_path_str)
        if db_path.parent and str(db_path.parent) not in ("", "."):
            db_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    logger.info("Database engine initialized: %s", url)
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=Session,
        )
    return _SessionFactory


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Import models so they register with Base.metadata before create_all.
    from app.storage import models as _models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
    logger.info("Database schema ensured.")


def drop_db() -> None:
    """Drop all tables. Used by reset scripts and tests only."""
    from app.storage import models as _models  # noqa: F401

    Base.metadata.drop_all(bind=get_engine())
    logger.warning("Database schema dropped.")


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()