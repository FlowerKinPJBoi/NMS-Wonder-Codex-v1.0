from __future__ import annotations

import re
from typing import Any

from ..models import AssetSighting, AssetSpecimen
from .catalog import public_contributor


SUPPORTED_ASSET_TYPES = {"Starship", "Freighter", "Frigate", "Multitool"}
SUPPORTED_SOURCE_ROLES = {
    "current", "owned_slot", "stored_slot", "fleet_member", "squadron_member",
    "archived", "historical", "template", "unknown",
}
ASSET_PREFIX = {"Starship": "SH", "Freighter": "FR", "Frigate": "FG", "Multitool": "MT"}
ASSET_ARCHETYPE = {
    "Starship": "asset.starship",
    "Freighter": "asset.freighter",
    "Frigate": "asset.frigate",
    "Multitool": "asset.multitool",
}
ASSET_KEY = re.compile(r"^PGA-[A-Z0-9-]+-[A-F0-9]{16}$", re.IGNORECASE)


class AssetManifestError(ValueError):
    pass


def asset_wc_id(asset: AssetSpecimen | int, asset_type: str | None = None) -> str:
    if isinstance(asset, AssetSpecimen):
        record_id, kind = asset.id, asset.asset_type
    else:
        record_id, kind = asset, asset_type or "Asset"
    return f"WC-{ASSET_PREFIX.get(kind, 'AS')}-{record_id:06d}"


def normalize_manifest(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    schema = str(manifest.get("schema", ""))
    if not schema.startswith("wonder-codex-pegasus-asset-manifest/"):
        raise AssetManifestError("This is not a supported Wonder Codex Pegasus asset manifest.")

    privacy = manifest.get("privacy")
    if not isinstance(privacy, dict):
        raise AssetManifestError("The manifest is missing its privacy declaration.")
    forbidden = [
        key for key in ("rawSaveUploaded", "rawSavePathIncluded", "accountIdentifiersIncluded", "inventoryCoordinatesIncluded")
        if privacy.get(key) is True
    ]
    if forbidden:
        raise AssetManifestError(f"Unsafe manifest privacy flags: {', '.join(forbidden)}.")

    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise AssetManifestError("The manifest assets value must be an array.")
    if len(assets) > 5000:
        raise AssetManifestError("The manifest contains too many asset records.")

    normalized: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    for source in assets:
        if not isinstance(source, dict):
            skipped["invalid_record"] = skipped.get("invalid_record", 0) + 1
            continue
        asset_type = str(source.get("assetType", ""))
        if asset_type not in SUPPORTED_ASSET_TYPES:
            key = asset_type or "unknown_type"
            skipped[key] = skipped.get(key, 0) + 1
            continue
        asset_key = str(source.get("assetKey", "")).upper()
        fields = source.get("fields")
        if not ASSET_KEY.fullmatch(asset_key) or not isinstance(fields, dict):
            skipped["invalid_identity"] = skipped.get("invalid_identity", 0) + 1
            continue

        raw_ordinal = source.get("sourceOrdinal", fields.get("sourceOrdinal"))
        source_role = str(source.get("sourceRole") or fields.get("sourceRole") or "unknown")
        if source_role not in SUPPORTED_SOURCE_ROLES:
            source_role = "unknown"
        special_signal = source.get("modifiedOrSpecialSignal", fields.get("modifiedOrSpecialSignal"))
        normalized.append({
            "asset_key": asset_key,
            "asset_type": asset_type,
            "display_name": str(source.get("displayName", ""))[:200],
            "source_role": source_role,
            "source_collection": str(source.get("sourceCollection") or fields.get("sourceCollection") or "")[:120],
            "source_ordinal": raw_ordinal if isinstance(raw_ordinal, int) and not isinstance(raw_ordinal, bool) and raw_ordinal >= 0 else None,
            "identity_basis": str(source.get("identityBasis") or fields.get("identityBasis") or "normalized_asset_key")[:120],
            "publication_state": "review",
            "confidence": str(source.get("confidence", "Beta extracted"))[:80],
            "modified_or_special_signal": special_signal is True,
            "delivery_eligibility": str(source.get("deliveryEligibility") or "research_only")[:60],
            "delivery_evidence_status": str(source.get("deliveryEvidenceStatus") or "not_evaluated")[:60],
            "fields": fields,
        })
    return normalized, skipped


def serialize_asset(
    asset: AssetSpecimen,
    sighting: AssetSighting | None = None,
    *,
    detail: bool = False,
    admin: bool = False,
) -> dict[str, Any]:
    fields = asset.fields or {}
    asset_class = str(fields.get("class", ""))
    class_provenance = str(fields.get("classProvenance", ""))
    native_class_known = fields.get("nativeClassKnown") is True
    class_label = asset_class
    if asset_class and not native_class_known and class_provenance in {"current_inventory", "current_fleet_record"}:
        class_label = f"{asset_class} · current"
    item: dict[str, Any] = {
        "id": asset.id,
        "wc_id": asset_wc_id(asset),
        "asset_key": asset.asset_key,
        "asset_type": asset.asset_type,
        "display_name": asset.display_name or f"{asset.asset_type} specimen {asset_wc_id(asset)}",
        "contributor": public_contributor(asset.contributor, asset.public_attribution),
        "platform": asset.platform,
        "source_role": asset.source_role,
        "source_collection": asset.source_collection,
        "source_ordinal": asset.source_ordinal,
        "identity_basis": asset.identity_basis,
        "publication_state": asset.publication_state,
        "confidence": asset.confidence,
        "modified_or_special_signal": asset.modified_or_special_signal,
        "delivery_eligibility": asset.delivery_eligibility,
        "delivery_evidence_status": asset.delivery_evidence_status,
        "image_status": asset.image_status,
        "primary_image_url": "",
        "archetype_key": ASSET_ARCHETYPE.get(asset.asset_type, "other.unknown"),
        "location_status": sighting.status if sighting else "unverified",
        "galaxy_number": sighting.galaxy_number if sighting else None,
        "galaxy_name": sighting.galaxy_name if sighting else "",
        "portal_glyphs": sighting.portal_glyphs if sighting else "",
        "has_location": bool(sighting and sighting.status == "verified" and sighting.galaxy_number and len(sighting.portal_glyphs) == 12),
        "class": asset_class,
        "class_label": class_label,
        "class_provenance": class_provenance,
        "native_class_known": native_class_known,
        "seed": str(fields.get("seed") or fields.get("resourceSeed") or ""),
        "resource_filename": str(fields.get("resourceFilename", "")),
        "identity_fingerprint": str(fields.get("identityFingerprint", "")),
        "identity_stability": str(fields.get("identityStability", "")),
        "appearance_seed_location_status": str(fields.get("appearanceSeedLocationStatus", "")),
        "home_system_evidence": str(fields.get("homeSystemEvidence", "")),
        "home_system_seed_meaning": str(fields.get("homeSystemSeedMeaning", "")),
        "created_at": asset.created_at.isoformat(),
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }
    if detail:
        item["fields"] = fields
        item["sighting"] = ({
            "id": sighting.id,
            "status": sighting.status,
            "galaxy_number": sighting.galaxy_number,
            "galaxy_name": sighting.galaxy_name,
            "portal_glyphs": sighting.portal_glyphs,
            "source": sighting.source,
        } if sighting else None)
    if admin:
        item["save_name"] = asset.save_name
        item["public_attribution"] = asset.public_attribution
        item["reviewer_note"] = asset.reviewer_note
        if sighting and item.get("sighting") is not None:
            item["sighting"]["notes"] = sighting.notes
            item["sighting"]["reviewer_note"] = sighting.reviewer_note
    return item
