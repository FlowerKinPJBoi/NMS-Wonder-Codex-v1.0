from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from fastapi import HTTPException

from app.services.daedalus import inspect_learning_package


def ship_source(objects: list[dict]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("objects.json", json.dumps(objects))
        archive.writestr("so.json", json.dumps({"Name": "Test Corvette"}))
        archive.writestr("ccd.json", json.dumps({}))
    return output.getvalue()


def incomplete_ship_source(objects: list[dict]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("objects.json", json.dumps(objects))
    return output.getvalue()


def object_record(object_id: str, *, up=None, at=None) -> dict:
    return {
        "ObjectID": object_id,
        "UserData": 0,
        "Position": [0, 0, 0],
        "Up": up or [0, 1, 0],
        "At": at or [0, 0, 1],
    }


def learning_package(*, objects=None, object_count=None, protected=None, source_format="nmsship") -> bytes:
    objects = objects or [object_record("^U_PARAGON"), object_record("^B_FLOOR"), object_record("^B_FLOOR")]
    source = ship_source(objects)
    counts: dict[str, int] = {}
    for item in objects:
        counts[item["ObjectID"]] = counts.get(item["ObjectID"], 0) + 1
    declared_count = object_count if object_count is not None else len(objects)
    if object_count is not None and object_count != len(objects):
        counts = {"^U_PARAGON": 1, "^B_FLOOR": object_count - 1}
    record = {
        "schema": "wonder-codex.daedalus.learning-record.v0.3",
        "recordId": "test-record-001",
        "domain": {"current": "NO_MANS_SKY_CORVETTE_BUILDING"},
        "designIntent": {"originalRequest": "A safe test ship"},
        "groundTruth": {
            "fileName": "test.nmsship",
            "format": source_format,
            "sha256": hashlib.sha256(source).hexdigest(),
            "objectCount": declared_count,
            "distinctObjectIds": len(counts),
            "partInventory": [{"objectId": key, "count": value} for key, value in counts.items()],
            "reverseBlueprint": {"build": {"name": "Test Corvette"}},
        },
        "teacherFeedback": {
            "groundTruth": {"status": "verified"},
            "generatedAttempt": {"status": "needs_correction"},
        },
        "trust": {"collection": "TRUSTED_SUPERVISED_CORRECTION", "eligibleForTraining": True},
        "safety": {
            "readOnlyAnalysis": True,
            "sourceModified": False,
            "saveAccessed": False,
            "packageMutationPerformed": False,
            "protectedObjectIds": protected if protected is not None else ["^U_PARAGON"],
        },
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("learning-record.json", json.dumps(record))
        archive.writestr("ground-truth/test.nmsship", source)
    return output.getvalue()


def base_wrapper_package() -> bytes:
    base_objects = [object_record("^BASE_FLAG")]
    source = json.dumps({"Objects": base_objects, "Prefabs": [{"PrefabID": "Lounge"}]}).encode()
    definition_objects = [object_record("^B_FLOOR"), object_record("^BUILDCHAIR4")]
    definition = json.dumps({"Prefab": definition_objects}).encode()
    record = {
        "schema": "wonder-codex.daedalus.learning-record.v0.3",
        "recordId": "base-wrapper-001",
        "domain": {"current": "NO_MANS_SKY_BASE_BUILDING"},
        "designIntent": {"originalRequest": "A safe base wrapper"},
        "groundTruth": {
            "fileName": "base.NMSBASE",
            "format": "nmsbase",
            "sha256": hashlib.sha256(source).hexdigest(),
            "objectCount": 3,
            "distinctObjectIds": 3,
            "partInventory": [
                {"objectId": "^BASE_FLAG", "count": 1},
                {"objectId": "^B_FLOOR", "count": 1},
                {"objectId": "^BUILDCHAIR4", "count": 1},
            ],
            "prefabInstances": [{"PrefabID": "Lounge"}],
            "prefabDefinitions": [{
                "fileName": "Lounge.nmsprefab",
                "sha256": hashlib.sha256(definition).hexdigest(),
                "objectCount": 2,
            }],
        },
        "teacherFeedback": {"groundTruth": {"status": "verified"}},
        "trust": {"collection": "TRUSTED_GROUND_TRUTH"},
        "safety": {
            "readOnlyAnalysis": True,
            "sourceModified": False,
            "saveAccessed": False,
            "packageMutationPerformed": False,
            "protectedObjectIds": ["^BASE_FLAG"],
        },
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("learning-record.json", json.dumps(record))
        archive.writestr("ground-truth/base.nmsbase", source)
        archive.writestr("ground-truth/prefab-definitions/Lounge.nmsprefab", definition)
    return output.getvalue()


def test_valid_learning_package_is_server_checked_but_not_auto_released():
    package = inspect_learning_package(learning_package(), "teacher.zip", maximum_bytes=5_000_000)
    assert package.summary["object_count"] == 3
    assert package.validation["passed"] is True
    assert package.validation["protectedObjectId"] == "^U_PARAGON"
    assert package.validation["serverReleaseRequired"] is True


def test_learning_package_rejects_more_than_3000_parts():
    with pytest.raises(HTTPException, match="1–3,000"):
        inspect_learning_package(learning_package(object_count=3001), "too-large.zip", maximum_bytes=5_000_000)


def test_learning_package_rejects_non_uniform_stretching():
    objects = [
        object_record("^U_PARAGON"),
        object_record("^B_FLOOR", up=[0, 0.4, 0], at=[0, 0, 1]),
    ]
    with pytest.raises(HTTPException, match="non-uniform scale"):
        inspect_learning_package(learning_package(objects=objects), "stretched.zip", maximum_bytes=5_000_000)


def test_learning_package_requires_protected_corvette_anchor_policy():
    with pytest.raises(HTTPException, match=r"protect \^U_PARAGON"):
        inspect_learning_package(learning_package(protected=[]), "unsafe.zip", maximum_bytes=5_000_000)


def test_learning_package_rejects_unsafe_zip_paths():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../learning-record.json", "{}")
    with pytest.raises(HTTPException, match="unsafe file path"):
        inspect_learning_package(output.getvalue(), "unsafe-path.zip", maximum_bytes=5_000_000)


def test_client_training_claim_never_changes_server_release_requirement():
    package = inspect_learning_package(learning_package(), "candidate.zip", maximum_bytes=5_000_000)
    assert package.record["trust"]["eligibleForTraining"] is True
    assert package.validation["serverReleaseRequired"] is True


def test_nmsbase_wrapper_validates_base_flag_and_prefab_geometry_separately():
    package = inspect_learning_package(base_wrapper_package(), "base-learning.zip", maximum_bytes=5_000_000)
    assert package.validation["protectedObjectId"] == "^BASE_FLAG"
    assert package.validation["protectedObjectVerifiedInSource"] is True
    assert package.validation["prefabDefinitionGeometryVerified"] is True


def test_corvette_source_requires_complete_nmsship_package():
    objects = [object_record("^U_PARAGON"), object_record("^B_FLOOR")]
    source = incomplete_ship_source(objects)
    record = {
        "schema": "wonder-codex.daedalus.learning-record.v0.3",
        "recordId": "incomplete-ship",
        "domain": {"current": "NO_MANS_SKY_CORVETTE_BUILDING"},
        "groundTruth": {
            "fileName": "incomplete.nmsship",
            "format": "nmsship",
            "sha256": hashlib.sha256(source).hexdigest(),
            "objectCount": 2,
            "distinctObjectIds": 2,
            "partInventory": [
                {"objectId": "^U_PARAGON", "count": 1},
                {"objectId": "^B_FLOOR", "count": 1},
            ],
        },
        "safety": {
            "readOnlyAnalysis": True,
            "sourceModified": False,
            "saveAccessed": False,
            "packageMutationPerformed": False,
            "protectedObjectIds": ["^U_PARAGON"],
        },
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("learning-record.json", json.dumps(record))
        archive.writestr("ground-truth/incomplete.nmsship", source)
    with pytest.raises(HTTPException, match="missing required package entries"):
        inspect_learning_package(output.getvalue(), "incomplete.zip", maximum_bytes=5_000_000)


def test_source_records_require_finite_positions():
    objects = [object_record("^U_PARAGON"), object_record("^B_FLOOR")]
    objects[1]["Position"] = [0, float("inf"), 0]
    with pytest.raises(HTTPException, match="valid Object IDs or positions"):
        inspect_learning_package(learning_package(objects=objects), "bad-position.zip", maximum_bytes=5_000_000)
