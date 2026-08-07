from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.daedalus_corpus import extract_lesson, score_entry


def submission(**overrides):
    values = {
        "id": "submission-1",
        "record_id": "record-1",
        "domain": "NO_MANS_SKY_BASE_BUILDING",
        "ground_truth_format": "nmsbase",
        "object_count": 42,
        "distinct_object_ids": 4,
        "trust_collection": "TRUSTED_SUPERVISED_CORRECTION",
        "sha256": "a" * 64,
        "original_filename": "lesson.zip",
        "contributor": "Krosskelt",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def record():
    return {
        "designIntent": {
            "originalRequest": "Decorate a narrow alloy lounge while preserving the central walkway.",
            "styleTags": ["alloy", "lounge", "clear walkway"],
            "recognizedCategory": "interior decoration",
        },
        "groundTruth": {
            "format": "nmsbase",
            "bounds": {"size": [32, 8, 48]},
            "partInventory": [
                {"objectId": "^BASE_FLAG", "count": 1},
                {"objectId": "^BUILDCHAIR4", "count": 8},
                {"objectId": "^BUILDTABLE", "count": 2},
            ],
            "reverseBlueprint": {"build": {"patterns": {"grids": ["edge seating"]}}},
        },
        "teacherFeedback": {
            "note": "In this room, keep furniture near the walls and leave the center clear.",
            "groundTruth": {"status": "verified"},
            "generatedAttempt": {"status": "needs_correction"},
            "partFeedback": [{"explanation": "Chair faced away from its table."}],
        },
        "conversationalRevisions": [{"instruction": "Rotate chairs toward the table."}],
        "conversation": [{"content": "This is contextual guidance, not a universal never rule."}],
        "referenceEvidence": [{"data": "raw-image-evidence-must-not-enter-the-corpus"}],
        "trust": {"collection": "TRUSTED_SUPERVISED_CORRECTION"},
        "safety": {"protectedObjectIds": ["^BASE_FLAG"]},
    }


def test_extract_lesson_keeps_compact_learning_and_private_evidence_out():
    semantic, fingerprint, lesson, provenance = extract_lesson(
        record(), submission(), actor="PJ", release_note="Compared with the in-game result."
    )
    assert "central walkway" in semantic
    assert "^BUILDCHAIR4" in semantic
    assert fingerprint["objectIds"] == ["^BASE_FLAG", "^BUILDCHAIR4", "^BUILDTABLE"]
    assert lesson["corrections"]["teacherNote"].startswith("In this room")
    assert lesson["groundTruth"]["partInventory"][1]["count"] == 8
    assert provenance["sourceSha256"] == "a" * 64
    serialized = json.dumps({"lesson": lesson, "provenance": provenance})
    assert "raw-image-evidence-must-not-enter-the-corpus" not in serialized


def test_structural_and_semantic_match_outscores_unrelated_lesson():
    relevant = SimpleNamespace(
        semantic_text="alloy lounge chairs tables preserve clear central walkway",
        recognized_category="interior decoration",
        structural_fingerprint={
            "styleTags": ["alloy", "lounge"],
            "objectIds": ["^BUILDCHAIR4", "^BUILDTABLE"],
            "objectCount": 40,
        },
    )
    unrelated = SimpleNamespace(
        semantic_text="hot pink convertible beetle corvette",
        recognized_category="vehicle",
        structural_fingerprint={
            "styleTags": ["convertible"],
            "objectIds": ["^U_PARAGON"],
            "objectCount": 1500,
        },
    )
    request = {
        "query": "decorate alloy lounge with a clear walkway",
        "category": "interior decoration",
        "style_tags": ["alloy", "lounge"],
        "object_ids": ["^BUILDCHAIR4", "^BUILDTABLE"],
        "part_count": 42,
    }
    relevant_score, reasons = score_entry(relevant, **request)
    unrelated_score, _ = score_entry(unrelated, **request)
    assert relevant_score > unrelated_score
    assert "same build category" in reasons
    assert any(reason.startswith("Object ID overlap") for reason in reasons)
