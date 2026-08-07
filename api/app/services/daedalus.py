from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

from ..config import get_settings

logger = logging.getLogger(__name__)
ALLOWED_SCHEMAS = {
    "wonder-codex.daedalus.learning-record.v0.2",
    "wonder-codex.daedalus.learning-record.v0.3",
}
ALLOWED_DOMAINS = {
    "NO_MANS_SKY_CORVETTE_BUILDING",
    "NO_MANS_SKY_BASE_BUILDING",
}
MAX_MEMBERS = 250
MAX_EXPANDED_BYTES = 180 * 1024 * 1024
MAX_JSON_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class PreparedLearningPackage:
    body: bytes
    sha256: str
    filename: str
    record: dict[str, Any]
    summary: dict[str, Any]
    validation: dict[str, Any]


def safe_package_filename(value: str) -> str:
    name = PurePosixPath((value or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._+-]+", "-", name).strip("-.")[:220]
    if not stem:
        stem = "daedalus-learning-package.zip"
    if not stem.lower().endswith(".zip"):
        stem += ".zip"
    return stem[:255]


def _safe_archive_member_name(value: str) -> str:
    normalized = value.replace("\\", "/")
    name = PurePosixPath(normalized).name
    if not name or name != normalized:
        raise HTTPException(status_code=400, detail="The ground-truth fileName must be a plain file name.")
    if "." in name:
        stem, extension = name.rsplit(".", 1)
        safe_stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", stem).strip() or "file"
        return f"{safe_stem}.{extension.lower()}"
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip() or "file"


def _safe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(normalized and not normalized.startswith("/") and ".." not in path.parts)


def _json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    if len(raw) > MAX_JSON_BYTES:
        raise HTTPException(status_code=400, detail=f"{label} is too large.")
    try:
        parsed = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} is not valid UTF-8 JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail=f"{label} must be a JSON object.")
    return parsed


def _read_zip_member(raw: bytes, member: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return archive.read(member)
    except (zipfile.BadZipFile, KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail="The ZIP failed its integrity check.") from exc


def _find_objects(value: Any, depth: int = 0) -> list[dict[str, Any]] | None:
    if depth > 6 or value is None:
        return None
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value) and any("ObjectID" in item for item in value):
            return value
        return None
    if not isinstance(value, dict):
        return None
    for key in ("Objects", "objects", "Prefab", "PersistentBaseObjects", "PlacedObjects"):
        candidate = value.get(key)
        if isinstance(candidate, list) and (not candidate or any(isinstance(item, dict) and "ObjectID" in item for item in candidate)):
            return candidate
    for child in value.values():
        found = _find_objects(child, depth + 1)
        if found is not None:
            return found
    return None


def _objects_from_source(source: bytes, source_format: str) -> list[dict[str, Any]] | None:
    if source_format == "nmsship":
        try:
            with zipfile.ZipFile(io.BytesIO(source)) as ship:
                match = next((name for name in ship.namelist() if name.lower().endswith("objects.json")), None)
                if not match:
                    return None
                parsed = json.loads(ship.read(match).decode("utf-8-sig"))
                return parsed if isinstance(parsed, list) else None
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError):
            return None
    try:
        parsed = json.loads(source.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _find_objects(parsed)


def _verify_ship_package(source: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(source)) as ship:
            names = {PurePosixPath(name.replace("\\", "/")).name.casefold() for name in ship.namelist()}
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="The Corvette ground truth is not a readable .nmsship package.") from exc
    missing = {"objects.json", "so.json", "ccd.json"} - names
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"The Corvette ground truth is missing required package entries: {', '.join(sorted(missing))}.",
        )


def _vector_length(value: Any) -> float | None:
    if not isinstance(value, list) or len(value) < 3:
        return None
    try:
        numbers = [float(value[index]) for index in range(3)]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(number) for number in numbers):
        return None
    return math.sqrt(sum(number * number for number in numbers))


def _valid_position(value: Any) -> bool:
    if not isinstance(value, list) or len(value) < 3:
        return False
    try:
        numbers = [float(value[index]) for index in range(3)]
    except (TypeError, ValueError):
        return False
    return all(math.isfinite(number) for number in numbers)


def _non_uniform_indices(objects: list[dict[str, Any]]) -> list[int]:
    invalid: list[int] = []
    for index, item in enumerate(objects):
        up = _vector_length(item.get("Up"))
        at = _vector_length(item.get("At"))
        if up is None or at is None or up <= 0 or at <= 0:
            invalid.append(index)
            continue
        tolerance = max(0.005, max(up, at) * 0.01)
        if abs(up - at) > tolerance:
            invalid.append(index)
    return invalid


def inspect_learning_package(raw: bytes, filename: str, *, maximum_bytes: int) -> PreparedLearningPackage:
    if not raw:
        raise HTTPException(status_code=400, detail="The learning package is empty.")
    if len(raw) > maximum_bytes:
        raise HTTPException(status_code=413, detail="The learning package exceeds the configured upload limit.")
    digest = hashlib.sha256(raw).hexdigest()
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Daedalus learning packages must be complete, readable ZIP files.") from exc

    with archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if not members or len(members) > MAX_MEMBERS:
            raise HTTPException(status_code=400, detail=f"Learning packages must contain 1–{MAX_MEMBERS} files.")
        if any(not _safe_member(item.filename) for item in members):
            raise HTTPException(status_code=400, detail="The ZIP contains an unsafe file path.")
        if any(item.flag_bits & 0x1 for item in members):
            raise HTTPException(status_code=400, detail="Encrypted ZIP members are not accepted.")
        if sum(item.file_size for item in members) > MAX_EXPANDED_BYTES:
            raise HTTPException(status_code=400, detail="The expanded learning package is too large.")
        names = {item.filename.casefold(): item.filename for item in members}
        if len(names) != len(members):
            raise HTTPException(status_code=400, detail="The ZIP contains duplicate file names.")
        record_name = names.get("learning-record.json")
        if not record_name:
            raise HTTPException(status_code=400, detail="learning-record.json is missing from the package root.")
        try:
            record = _json_object(archive.read(record_name), label="learning-record.json")
        except (KeyError, RuntimeError, zipfile.BadZipFile) as exc:
            raise HTTPException(status_code=400, detail="The ZIP failed its integrity check.") from exc

        schema = str(record.get("schema") or "")
        if schema not in ALLOWED_SCHEMAS:
            raise HTTPException(status_code=400, detail="This Daedalus learning-record schema is not supported.")
        record_id = str(record.get("recordId") or "").strip()
        if not record_id or len(record_id) > 120:
            raise HTTPException(status_code=400, detail="The learning record needs a valid recordId.")
        domain_data = record.get("domain") if isinstance(record.get("domain"), dict) else {}
        domain = str(domain_data.get("current") or "")
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=400, detail="The learning record is outside Daedalus Builder's allowed NMS domains.")

        ground = record.get("groundTruth") if isinstance(record.get("groundTruth"), dict) else {}
        try:
            object_count = int(ground.get("objectCount"))
            distinct_count = int(ground.get("distinctObjectIds"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Ground-truth object counts are invalid.") from exc
        if object_count < 1 or object_count > 3000:
            raise HTTPException(status_code=400, detail="Ground truth must contain 1–3,000 placed objects.")
        if distinct_count < 1 or distinct_count > object_count:
            raise HTTPException(status_code=400, detail="The distinct Object ID count is invalid.")

        inventory = ground.get("partInventory")
        if not isinstance(inventory, list) or len(inventory) != distinct_count:
            raise HTTPException(status_code=400, detail="The part inventory does not match the distinct Object ID count.")
        inventory_total = 0
        inventory_ids: set[str] = set()
        for part in inventory:
            if not isinstance(part, dict):
                raise HTTPException(status_code=400, detail="Every part inventory entry must be an object.")
            object_id = str(part.get("objectId") or "")
            try:
                count = int(part.get("count"))
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="A part inventory count is invalid.") from exc
            if not object_id.startswith("^") or count < 1 or object_id in inventory_ids:
                raise HTTPException(status_code=400, detail="The part inventory contains an invalid or duplicate Object ID.")
            inventory_ids.add(object_id)
            inventory_total += count
        if inventory_total != object_count:
            raise HTTPException(status_code=400, detail="The part inventory total does not match objectCount.")

        source_name = str(ground.get("fileName") or "").strip()
        source_format = str(ground.get("format") or "").strip().lower().lstrip(".")
        if source_format not in {"nmsship", "nmsbase", "nmsprefab", "json"}:
            raise HTTPException(status_code=400, detail="The ground-truth source format is not supported.")
        archive_source_name = _safe_archive_member_name(source_name)
        source_member = names.get(f"ground-truth/{archive_source_name}".casefold())
        if not source_member:
            suffix = f"/{archive_source_name}".casefold()
            source_member = next((real for folded, real in names.items() if folded.endswith(suffix)), None)
        if not source_member:
            raise HTTPException(status_code=400, detail="The declared ground-truth source file is missing from the ZIP.")
        source = archive.read(source_member)
        source_hash = hashlib.sha256(source).hexdigest()
        if source_hash.casefold() != str(ground.get("sha256") or "").casefold():
            raise HTTPException(status_code=400, detail="The ground-truth source SHA-256 does not match learning-record.json.")

    safety = record.get("safety") if isinstance(record.get("safety"), dict) else {}
    if safety.get("readOnlyAnalysis") is not True or any(
        safety.get(key) is not False for key in ("sourceModified", "saveAccessed", "packageMutationPerformed")
    ):
        raise HTTPException(status_code=400, detail="The package does not attest to Daedalus's read-only safety boundary.")
    protected = safety.get("protectedObjectIds") if isinstance(safety.get("protectedObjectIds"), list) else []
    required_anchor = None
    if domain == "NO_MANS_SKY_CORVETTE_BUILDING":
        required_anchor = "^U_PARAGON"
    elif source_format == "nmsbase" or "^BASE_FLAG" in inventory_ids:
        required_anchor = "^BASE_FLAG"
    if required_anchor and required_anchor not in protected:
        raise HTTPException(status_code=400, detail=f"The safety record must protect {required_anchor}.")

    prefab_instances = ground.get("prefabInstances") if isinstance(ground.get("prefabInstances"), list) else []
    if source_format == "nmsship":
        _verify_ship_package(source)
    objects = _objects_from_source(source, source_format)
    if objects is None:
        raise HTTPException(status_code=400, detail="The ground-truth source has no readable Object ID geometry.")
    scale_failures: list[int] = []
    if objects is not None:
        malformed = [
            index
            for index, item in enumerate(objects)
            if not isinstance(item, dict)
            or not str(item.get("ObjectID") or "").startswith("^")
            or not _valid_position(item.get("Position"))
        ]
        if malformed:
            raise HTTPException(status_code=400, detail="The source contains placed records without valid Object IDs or positions.")
        actual_ids = {str(item.get("ObjectID")) for item in objects}
        if prefab_instances:
            if not actual_ids.issubset(inventory_ids):
                raise HTTPException(status_code=400, detail="The wrapper source contains Object IDs outside the declared inventory.")
        elif len(objects) != object_count:
            raise HTTPException(status_code=400, detail="The source placed-object count does not match learning-record.json.")
        elif actual_ids != inventory_ids:
            raise HTTPException(status_code=400, detail="The source Object IDs do not match the declared part inventory.")
        if required_anchor:
            anchor_count = sum(1 for item in objects if item.get("ObjectID") == required_anchor)
            if anchor_count != 1:
                raise HTTPException(status_code=400, detail=f"The source must contain exactly one {required_anchor} record.")
        scale_failures = _non_uniform_indices(objects)
        if scale_failures:
            raise HTTPException(
                status_code=400,
                detail=f"{len(scale_failures)} source records use missing or non-uniform scale; NMS Object ID parts must retain their normal shape.",
            )

    prefab_geometry_verified = False
    if prefab_instances:
        definitions = ground.get("prefabDefinitions") if isinstance(ground.get("prefabDefinitions"), list) else []
        if not definitions:
            raise HTTPException(status_code=400, detail="A named-prefab wrapper must include its prefab definition evidence.")
        for definition in definitions:
            if not isinstance(definition, dict):
                raise HTTPException(status_code=400, detail="Prefab definition evidence is invalid.")
            definition_name = _safe_archive_member_name(str(definition.get("fileName") or ""))
            member = names.get(f"ground-truth/prefab-definitions/{definition_name}".casefold())
            if not member:
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} is missing from the ZIP.")
            definition_source = _read_zip_member(raw, member)
            if hashlib.sha256(definition_source).hexdigest().casefold() != str(definition.get("sha256") or "").casefold():
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} failed its SHA-256 check.")
            definition_objects = _objects_from_source(definition_source, "nmsprefab")
            if definition_objects is None:
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} has no readable Object ID geometry.")
            if len(definition_objects) != int(definition.get("objectCount") or -1):
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} has an object-count mismatch.")
            definition_ids = {str(item.get("ObjectID") or "") for item in definition_objects}
            if not definition_ids or not all(item.startswith("^") for item in definition_ids) or not definition_ids.issubset(inventory_ids):
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} contains undeclared Object IDs.")
            if _non_uniform_indices(definition_objects):
                raise HTTPException(status_code=400, detail=f"Prefab definition {definition_name} contains non-uniformly scaled parts.")
        prefab_geometry_verified = True

    teacher = record.get("teacherFeedback") if isinstance(record.get("teacherFeedback"), dict) else {}
    ground_feedback = teacher.get("groundTruth") if isinstance(teacher.get("groundTruth"), dict) else {}
    attempt_feedback = teacher.get("generatedAttempt") if isinstance(teacher.get("generatedAttempt"), dict) else {}
    trust = record.get("trust") if isinstance(record.get("trust"), dict) else {}
    design_intent = record.get("designIntent") if isinstance(record.get("designIntent"), dict) else {}
    reverse = ground.get("reverseBlueprint") if isinstance(ground.get("reverseBlueprint"), dict) else {}
    build = reverse.get("build") if isinstance(reverse.get("build"), dict) else {}
    summary = {
        "schema_name": schema,
        "record_id": record_id,
        "domain": domain,
        "build_name": str(ground.get("buildName") or build.get("name") or source_name)[:200],
        "ground_truth_format": source_format,
        "object_count": object_count,
        "distinct_object_ids": distinct_count,
        "ground_truth_status": str(ground_feedback.get("status") or "unverified")[:40],
        "attempt_status": str(attempt_feedback.get("status") or "unreviewed")[:40],
        "trust_collection": str(trust.get("collection") or "QUARANTINED_UNVERIFIED_GROUND_TRUTH")[:100],
        "design_intent": design_intent,
    }
    validation = {
        "passed": True,
        "schemaAccepted": True,
        "sourceSha256Matched": True,
        "objectIdsOnly": True,
        "objectCountWithinLimit": True,
        "protectedObjectId": required_anchor,
        "protectedObjectVerifiedInSource": bool(required_anchor and objects is not None),
        "uniformScaleVerifiedInSource": objects is not None and (not prefab_instances or prefab_geometry_verified),
        "prefabDefinitionGeometryVerified": prefab_geometry_verified,
        "serverReleaseRequired": True,
    }
    return PreparedLearningPackage(
        body=raw,
        sha256=digest,
        filename=safe_package_filename(filename),
        record=record,
        summary=summary,
        validation=validation,
    )


def _client():
    settings = get_settings()
    if not settings.spaces_private_ready:
        raise HTTPException(status_code=503, detail="Private Daedalus storage is not configured yet.")
    return boto3.client(
        "s3",
        region_name=settings.spaces_region,
        endpoint_url=settings.spaces_endpoint,
        aws_access_key_id=settings.spaces_access_key,
        aws_secret_access_key=settings.spaces_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def store_learning_package(object_key: str, package: PreparedLearningPackage, actor: str) -> None:
    settings = get_settings()
    try:
        _client().put_object(
            Bucket=settings.spaces_bucket,
            Key=object_key,
            Body=package.body,
            ACL="private",
            ContentType="application/zip",
            CacheControl="private, no-store",
            ContentDisposition=f'attachment; filename="{package.filename}"',
            Metadata={"sha256": package.sha256, "contributor": re.sub(r"[^A-Za-z0-9._+-]+", "-", actor)[:80]},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not store Daedalus package %s", object_key)
        raise HTTPException(status_code=502, detail="Private storage did not accept the Daedalus package.") from exc


def verify_learning_package(object_key: str, *, expected_sha256: str, expected_size: int) -> None:
    settings = get_settings()
    try:
        stored = _client().head_object(Bucket=settings.spaces_bucket, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not verify Daedalus package %s", object_key)
        raise HTTPException(status_code=502, detail="The stored Daedalus package could not be verified.") from exc
    metadata = stored.get("Metadata") if isinstance(stored.get("Metadata"), dict) else {}
    if metadata.get("sha256", "").casefold() != expected_sha256.casefold() or int(stored.get("ContentLength") or -1) != expected_size:
        raise HTTPException(status_code=409, detail="The stored Daedalus package no longer matches its reviewed digest and size.")


def signed_learning_url(object_key: str, filename: str) -> str:
    settings = get_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.spaces_bucket,
                "Key": object_key,
                "ResponseContentType": "application/zip",
                "ResponseContentDisposition": f'attachment; filename="{safe_package_filename(filename)}"',
            },
            ExpiresIn=settings.daedalus_download_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Could not sign Daedalus package download %s", object_key)
        raise HTTPException(status_code=502, detail="Could not create a private Daedalus download.") from exc
