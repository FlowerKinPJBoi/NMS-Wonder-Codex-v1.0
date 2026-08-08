from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import REQUIRED_DATABASE_REVISION, check_database, state
from app.routers import daedalus


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://paypal.me/Daedalus", "https://paypal.me/Daedalus"),
        ("https://cash.app/example-payment-link", "https://cash.app/example-payment-link"),
        ("http://paypal.me/Daedalus", ""),
        ("https://user:secret@example.com/support", ""),
        ("javascript:alert(1)", ""),
        ("", ""),
    ],
)
def test_daedalus_support_link_accepts_only_safe_https_urls(value, expected):
    assert daedalus._safe_support_url(value) == expected


def test_build_schema_preflight_reports_missing_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with Session(engine) as session:
        with pytest.raises(HTTPException) as raised:
            daedalus._require_build_schema(session)
    assert raised.value.status_code == 503
    assert "0015_daedalus_build_jobs" in raised.value.detail


def test_build_schema_preflight_accepts_all_build_tables():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE daedalus_build_sessions (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE daedalus_build_passes (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE daedalus_build_jobs (id VARCHAR(36) PRIMARY KEY)"))
    with Session(engine) as session:
        daedalus._require_build_schema(session)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class _Connection:
    def __init__(self, revision):
        self.revision = revision

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, statement):
        if "alembic_version" in str(statement):
            return _Result([(self.revision,)] if self.revision else [])
        return _Result([(1,)])


def test_health_database_check_requires_deployed_schema_head(monkeypatch):
    monkeypatch.setattr("app.database.get_engine", lambda: SimpleNamespace(
        connect=lambda: _Connection("0012_daedalus_corpus")
    ))
    assert check_database() is False
    assert state.ready is False
    assert state.revision == "0012_daedalus_corpus"
    assert REQUIRED_DATABASE_REVISION in state.detail


def test_health_database_check_accepts_required_schema_head(monkeypatch):
    monkeypatch.setattr("app.database.get_engine", lambda: SimpleNamespace(
        connect=lambda: _Connection(REQUIRED_DATABASE_REVISION)
    ))
    assert check_database() is True
    assert state.ready is True
    assert state.revision == REQUIRED_DATABASE_REVISION
