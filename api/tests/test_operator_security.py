from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.services.security import require_admin_key, require_operator_key, require_owner_key


def configure_keys(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEYS", '{"PJ":"pj-secret","Boots":"boots-secret"}')
    monkeypatch.setenv("TESTER_API_KEY_MENOMOO", "meno-secret")
    monkeypatch.setenv("TESTER_API_KEY_FLOPPYDONKEY", "floppy-secret")
    monkeypatch.setenv("TESTER_API_KEY_DARKBELLATOR", "dark-secret")
    monkeypatch.setenv("TESTER_API_KEY_OLGRAVYLEG", "gravy-secret")
    monkeypatch.setenv("TESTER_API_KEY_MONKETSU", "monk-secret")
    monkeypatch.setenv("TESTER_API_KEY_READYFIREAIM", "ready-secret")
    monkeypatch.setenv("TESTER_API_KEY_VISCERAL", "visceral-secret")
    monkeypatch.setenv("TESTER_API_KEY_KROSSKELT", "kross-secret")
    get_settings.cache_clear()


def test_tester_receives_download_transit_and_capture_scopes_only(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("meno-secret", "Menomoo")
    assert session.actor == "Menomoo"
    assert session.scopes == frozenset({"apps:download", "transit", "capture:submit"})
    assert session.can_upload_private_apps is False
    get_settings.cache_clear()


def test_tester_key_cannot_enter_admin_review_console(monkeypatch):
    configure_keys(monkeypatch)
    with pytest.raises(HTTPException) as error:
        require_admin_key("meno-secret", "Menomoo")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_monketsu_receives_restricted_app_and_transit_access(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("monk-secret", "Monketsu")
    assert session.actor == "Monketsu"
    assert session.scopes == frozenset({"apps:download", "transit", "capture:submit"})
    assert session.can_upload_private_apps is False

    with pytest.raises(HTTPException) as error:
        require_admin_key("monk-secret", "Monketsu")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_readyfireaim_receives_restricted_app_and_transit_access(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("ready-secret", "ReadyFireAim")
    assert session.actor == "ReadyFireAim"
    assert session.scopes == frozenset({"apps:download", "transit", "capture:submit"})
    assert session.can_upload_private_apps is False

    with pytest.raises(HTTPException) as error:
        require_admin_key("ready-secret", "ReadyFireAim")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_visceral_receives_restricted_app_and_transit_access(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("visceral-secret", "Visceral")
    assert session.actor == "Visceral"
    assert session.scopes == frozenset({"apps:download", "transit", "capture:submit"})
    assert session.can_upload_private_apps is False

    with pytest.raises(HTTPException) as error:
        require_admin_key("visceral-secret", "Visceral")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_admin_keeps_all_operator_capabilities(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("pj-secret", "PJ")
    assert session.can_upload_private_apps is True
    assert {"admin", "apps:download", "apps:upload", "transit", "capture:submit", "daedalus:submit", "daedalus:review", "daedalus:release"} <= session.scopes
    get_settings.cache_clear()


def test_krosskelt_can_train_daedalus_without_review_or_admin(monkeypatch):
    configure_keys(monkeypatch)
    session = require_operator_key("kross-secret", "Krosskelt")
    assert "daedalus:submit" in session.scopes
    assert "daedalus:review" not in session.scopes
    assert "daedalus:release" not in session.scopes
    assert "admin" not in session.scopes
    get_settings.cache_clear()


def test_daedalus_allowlists_are_configurable_without_new_roles(monkeypatch):
    configure_keys(monkeypatch)
    monkeypatch.setenv("DAEDALUS_TRAINER_ACTORS", "PJ,Boots,Menomoo")
    monkeypatch.setenv("DAEDALUS_REVIEWER_ACTORS", "Boots")
    get_settings.cache_clear()
    trainer = require_operator_key("meno-secret", "Menomoo")
    pj = require_operator_key("pj-secret", "PJ")
    boots = require_operator_key("boots-secret", "Boots")
    assert "daedalus:submit" in trainer.scopes
    assert "daedalus:review" not in pj.scopes
    assert {"daedalus:submit", "daedalus:review", "daedalus:release"} <= boots.scopes
    get_settings.cache_clear()


def test_obsolete_malformed_json_variable_cannot_break_startup(monkeypatch):
    monkeypatch.setenv("TESTER_API_KEYS", "{not-digitalocean-json}")
    monkeypatch.setenv("TESTER_API_KEY_MENOMOO", "meno-secret")
    get_settings.cache_clear()
    session = require_operator_key("meno-secret", "Menomoo")
    assert session.actor == "Menomoo"
    get_settings.cache_clear()


def test_pj_named_key_unlocks_owner_analytics(monkeypatch):
    configure_keys(monkeypatch)
    session = require_owner_key("pj-secret", "PJ")
    assert session.actor == "PJ"
    assert "owner:analytics" in session.scopes
    get_settings.cache_clear()


def test_other_valid_admin_is_refused_owner_analytics(monkeypatch):
    configure_keys(monkeypatch)
    with pytest.raises(HTTPException) as error:
        require_owner_key("boots-secret", "Boots")
    assert error.value.status_code == 403
    get_settings.cache_clear()


def test_legacy_shared_key_cannot_claim_owner_identity(monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEYS", raising=False)
    monkeypatch.setenv("ADMIN_API_KEY", "legacy-secret")
    monkeypatch.setenv("ANALYTICS_OWNER_ACTOR", "PJ")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as error:
        require_owner_key("legacy-secret", "PJ")
    assert error.value.status_code == 401
    get_settings.cache_clear()
