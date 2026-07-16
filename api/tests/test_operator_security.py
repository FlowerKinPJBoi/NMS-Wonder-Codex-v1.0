from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.services.security import require_admin_key, require_operator_key


def configure_keys(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEYS", '{"PJ":"pj-secret"}')
    monkeypatch.setenv("TESTER_API_KEY_MENOMOO", "meno-secret")
    monkeypatch.setenv("TESTER_API_KEY_FLOPPYDONKEY", "floppy-secret")
    monkeypatch.setenv("TESTER_API_KEY_DARKBELLATOR", "dark-secret")
    monkeypatch.setenv("TESTER_API_KEY_OLGRAVYLEG", "gravy-secret")
    get_settings.cache_clear()


def test_tester_receives_download_and_transit_scopes_only(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("meno-secret", "Menomoo")
    assert session.actor == "Menomoo"
    assert session.scopes == frozenset({"apps:download", "transit"})
    assert session.can_upload_private_apps is False
    get_settings.cache_clear()


def test_tester_key_cannot_enter_admin_review_console(monkeypatch):
    configure_keys(monkeypatch)
    with pytest.raises(HTTPException) as error:
        require_admin_key("meno-secret", "Menomoo")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_admin_keeps_all_operator_capabilities(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("pj-secret", "PJ")
    assert session.can_upload_private_apps is True
    assert {"admin", "apps:download", "apps:upload", "transit"} <= session.scopes
    get_settings.cache_clear()


def test_obsolete_malformed_json_variable_cannot_break_startup(monkeypatch):
    monkeypatch.setenv("TESTER_API_KEYS", "{not-digitalocean-json}")
    monkeypatch.setenv("TESTER_API_KEY_MENOMOO", "meno-secret")
    get_settings.cache_clear()
    session = require_operator_key("meno-secret", "Menomoo")
    assert session.actor == "Menomoo"
    get_settings.cache_clear()
