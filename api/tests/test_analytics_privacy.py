from __future__ import annotations

from app.config import get_settings
from app.services.analytics import (
    classify_user_agent,
    clean_referrer,
    normalize_path,
    sanitize_properties,
    session_hash,
)


def test_admin_and_api_paths_are_never_tracked():
    assert normalize_path("/admin.html") is None
    assert normalize_path("/admin/analytics/") is None
    assert normalize_path("/api/stats") is None
    assert normalize_path("/record.html?id=42") == "/record.html"


def test_referrer_keeps_only_domain():
    assert clean_referrer("") == "Direct"
    assert clean_referrer("https://wondercodex.com/database.html?q=secret") == "Internal"
    assert clean_referrer("https://www.reddit.com/r/NoMansSky/?utm_source=test") == "www.reddit.com"


def test_properties_are_allowlisted_and_bounded():
    cleaned = sanitize_properties({
        "entity_id": "WC-A-000123",
        "query_kind": "text",
        "query_length": 18,
        "result_count": 5000000,
        "public_attribution": False,
        "decoder_result": "success",
        "raw_search_text": "should not be stored",
        "password": "never",
    })
    assert cleaned == {
        "entity_id": "WC-A-000123",
        "query_kind": "text",
        "query_length": 18,
        "result_count": 1_000_000,
        "public_attribution": False,
        "decoder_result": "success",
    }


def test_user_agent_is_reduced_to_coarse_families():
    agent = classify_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "Chrome/150.0.0.0 Safari/537.36"
    )
    assert agent == {
        "is_bot": False,
        "device_class": "Desktop",
        "browser_family": "Chrome",
        "os_family": "Windows",
    }
    assert classify_user_agent("Googlebot/2.1")["is_bot"] is True


def test_session_identifier_is_salted_before_storage(monkeypatch):
    monkeypatch.setenv("IP_HASH_SALT", "test-salt")
    get_settings.cache_clear()
    raw = "12345678-1234-1234-1234-123456789abc"
    hashed = session_hash(raw)
    assert hashed != raw
    assert len(hashed) == 64
    get_settings.cache_clear()
