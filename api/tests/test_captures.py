from __future__ import annotations

import pytest

from app.models import CaptureSubmission
from app.routers.captures import normalize_capture_discovery


def test_capture_model_is_registered():
    assert CaptureSubmission.__tablename__ == "capture_submissions"
    assert "discovery_record" in CaptureSubmission.__table__.columns
    assert "published_discovery_id" in CaptureSubmission.__table__.columns


def test_capture_normalization_retains_only_public_discovery_fields():
    normalized = normalize_capture_discovery({
        "DiscoveryType": "Animal",
        "UniversalAddress": "0x0011223344556677",
        "VP": [
            "0xA", "0xB", "0xC", "0xD", "0xE",
        ],
        "MessageID": "projector-message",
        "CreatureID": "^TREX",
        "CreatureType": "Trex",
        "Descriptors": ["^HEAD_1", "^TAIL_2"],
        "CustomName": "Mighty Friend",
        "Path": r"C:\Users\Private\save.hg",
        "AccountId": "must-not-leave-the-computer",
        "Inventory": {"Units": 999},
    })

    assert normalized == {
        "DT": "Animal",
        "UA": "0x0011223344556677",
        "VP0": "0xA",
        "VP1": "0xB",
        "VP2": "0xC",
        "VP3": "0xD",
        "VP4": "0xE",
        "MessageID": "projector-message",
        "CreatureID": "^TREX",
        "CreatureType": "Trex",
        "Descriptors": ["^HEAD_1", "^TAIL_2"],
        "CustomName": "Mighty Friend",
        "SensorEventID": "",
    }
    assert "Path" not in normalized
    assert "AccountId" not in normalized
    assert "Inventory" not in normalized


def test_capture_normalization_requires_location_and_type():
    with pytest.raises(ValueError, match="Universal Address"):
        normalize_capture_discovery({"DT": "Animal"})
