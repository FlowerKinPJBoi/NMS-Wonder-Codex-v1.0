from datetime import datetime, timezone

import pytest

from app.models import AssetSpecimen
from app.services.assets import AssetManifestError, asset_wc_id, normalize_manifest, serialize_asset


def manifest(asset_type="Starship", **overrides):
    asset = {
        "assetType": asset_type,
        "assetKey": "PGA-STARSHIP-0123456789ABCDEF",
        "displayName": "Procedural fighter starship",
        "sourceRole": "owned_slot",
        "sourceCollection": "ShipOwnership",
        "sourceOrdinal": 2,
        "identityBasis": "resource_filename_and_seed",
        "confidence": "Owned-asset seed",
        "deliveryEligibility": "acquisition_research",
        "deliveryEvidenceStatus": "location_not_evaluated",
        "fields": {"class": "S", "seed": "0x1234"},
    }
    asset.update(overrides)
    return {
        "schema": "wonder-codex-pegasus-asset-manifest/v0.2.1-beta",
        "privacy": {
            "rawSaveUploaded": False,
            "rawSavePathIncluded": False,
            "accountIdentifiersIncluded": False,
            "inventoryCoordinatesIncluded": False,
        },
        "assets": [asset],
    }


def test_normalize_manifest_retains_provenance_and_forces_review():
    records, skipped = normalize_manifest(manifest())
    assert skipped == {}
    assert records[0]["source_role"] == "owned_slot"
    assert records[0]["source_collection"] == "ShipOwnership"
    assert records[0]["source_ordinal"] == 2
    assert records[0]["publication_state"] == "review"


def test_normalize_manifest_rejects_raw_save_flags():
    payload = manifest()
    payload["privacy"]["rawSaveUploaded"] = True
    with pytest.raises(AssetManifestError, match="Unsafe manifest privacy flags"):
        normalize_manifest(payload)


def test_unsupported_asset_types_are_skipped():
    records, skipped = normalize_manifest(manifest("CompanionPet"))
    assert records == []
    assert skipped == {"CompanionPet": 1}


def test_unknown_source_role_is_safe_and_cannot_arrive_published():
    records, _ = normalize_manifest(manifest(sourceRole="invented", publicationState="published"))
    assert records[0]["source_role"] == "unknown"
    assert records[0]["publication_state"] == "review"


def test_asset_wc_ids_and_public_serialization():
    row = AssetSpecimen(
        id=12, asset_key="PGA-STARSHIP-0123456789ABCDEF", asset_type="Starship",
        display_name="Test ship", contributor="PJ", save_name="Test", platform="XB",
        public_attribution=True, source_role="owned_slot", source_collection="ShipOwnership",
        source_ordinal=0, identity_basis="resource_filename_and_seed", publication_state="published",
        confidence="Owned-asset seed", modified_or_special_signal=False,
        delivery_eligibility="acquisition_research", delivery_evidence_status="not_evaluated",
        image_status="needed", reviewer_note="", fields={"class": "S", "seed": "0x1234"},
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    assert asset_wc_id(row) == "WC-SH-000012"
    payload = serialize_asset(row)
    assert payload["archetype_key"] == "asset.starship"
    assert payload["class"] == "S"
    assert payload["primary_image_url"] == ""
