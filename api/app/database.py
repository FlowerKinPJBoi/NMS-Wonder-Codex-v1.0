from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


@dataclass
class DatabaseState:
    ready: bool = False
    detail: str = "Database has not been checked yet."
    checked_at: datetime | None = None


state = DatabaseState()
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        if not settings.sqlalchemy_database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        _engine = create_engine(
            settings.sqlalchemy_database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": settings.database_connect_timeout_seconds},
        )
        _SessionLocal = sessionmaker(
            bind=_engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _engine


def mark_database(ready: bool, detail: str) -> None:
    state.ready = ready
    state.detail = detail[:1000]
    state.checked_at = datetime.now(timezone.utc)


def check_database() -> bool:
    try:
        engine = get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        mark_database(True, "PostgreSQL connection successful.")
        return True
    except Exception as exc:  # service must stay alive to expose diagnostics
        logger.exception("Database readiness check failed")
        mark_database(False, f"{type(exc).__name__}: {exc}")
        return False


def get_session() -> Iterator[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
