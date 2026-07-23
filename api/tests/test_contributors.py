from __future__ import annotations

from datetime import datetime, timezone

from app.services.contributors import contributor_rank, contributor_slug, current_week


def test_contributor_rank_thresholds():
    assert contributor_rank(1)["code"] == "C"
    assert contributor_rank(50)["code"] == "B"
    assert contributor_rank(250)["code"] == "A"
    assert contributor_rank(1000)["code"] == "S"


def test_contributor_slug_is_public_url_safe():
    assert contributor_slug("Kuma The Wizard") == "kuma-the-wizard"
    assert contributor_slug("OlGravyLeg") == "olgravyleg"


def test_week_starts_on_monday_utc():
    start, end = current_week(datetime(2026, 7, 16, 14, 30, tzinfo=timezone.utc))
    assert start.isoformat() == "2026-07-13T00:00:00+00:00"
    assert (end - start).days == 7
