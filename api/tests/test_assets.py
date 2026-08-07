from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models import AssetSpecimen
from app.services.assets import AssetManifestError, asset_wc_id, normalize_manifest, serialize_asset
from app.services import forge as forge_service
from app.services.forge import forge_asset_representative_metadata


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
        "fields": {
            "class": "S",
            "classProvenance": "current_inventory",
            "nativeClassKnown": False,
            "seed": "0x1234",
            "identityFingerprint": "WCI-STARSHIP-0123456789ABCDEF0123",
            "identityStability": "procedural_identity_not_slot_position",
            "appearanceSeedLocationStatus": "not_a_location_claim",
        },
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
        image_status="needed", reviewer_note="", fields={
            "class": "S", "classProvenance": "current_inventory", "nativeClassKnown": False,
            "seed": "0x1234", "identityFingerprint": "WCI-STARSHIP-0123456789ABCDEF0123",
            "identityStability": "procedural_identity_not_slot_position",
            "appearanceSeedLocationStatus": "not_a_location_claim",
        },
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    assert asset_wc_id(row) == "WC-SH-000012"
    payload = serialize_asset(row)
    assert payload["archetype_key"] == "asset.starship"
    assert payload["class"] == "S"
    assert payload["class_label"] == "S · current"
    assert payload["class_provenance"] == "current_inventory"
    assert payload["native_class_known"] is False
    assert payload["identity_fingerprint"] == "WCI-STARSHIP-0123456789ABCDEF0123"
    assert payload["appearance_seed_location_status"] == "not_a_location_claim"
    assert payload["primary_image_url"] == ""
    assert "forge_image_url" not in payload


def test_unbound_spacecraft_forms_are_not_assigned_by_asset_type():
    starship = forge_asset_representative_metadata(SimpleNamespace(
        id=1, asset_key="PGA-STARSHIP-1111111111111111", asset_type="Starship",
    ))
    freighter = forge_asset_representative_metadata(SimpleNamespace(
        id=2, asset_key="PGA-FREIGHTER-2222222222222222", asset_type="Freighter",
    ))
    assert starship == {}
    assert freighter == {}


def test_spacecraft_form_requires_exact_identity_selector(monkeypatch):
    entry = {
        "id": "matched-fighter",
        "category_id": "starships",
        "family_id": "FIGHTER",
        "family_display": "Fighter",
        "form_name": "Matched fighter",
        "image_url": "assets/forge/catalog/starships/matched-fighter.webp",
        "record_eligible": True,
        "exact_specimen": False,
        "evidence_class": "identity_matched_reconstruction",
        "display_label": forge_service.MATCHED_IMAGE_LABEL,
        "ringless": True,
        "record_selectors": {
            "identity_fingerprints": ["WCI-STARSHIP-0123456789ABCDEF0123"],
        },
    }
    monkeypatch.setattr(forge_service, "CATALOG_ENTRIES", (entry,))
    metadata = forge_asset_representative_metadata(SimpleNamespace(
        id=1,
        asset_key="PGA-STARSHIP-1111111111111111",
        asset_type="Starship",
        fields={"identityFingerprint": "WCI-STARSHIP-0123456789ABCDEF0123"},
    ))
    assert metadata["forge_image_url"].endswith("matched-fighter.webp")
    assert metadata["forge_selection_basis"] == "explicit_catalog_record_selector"
