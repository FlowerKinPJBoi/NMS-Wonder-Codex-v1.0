from datetime import datetime, timezone

from app.models import Discovery, PetDiscoveryMatch
from app.schemas import CatalogUpdate, LocationVerificationPayload
from app.services.archetypes import archetype_metadata, discovery_match_key
from app.services.catalog import serialize_discovery, wc_id
from app.services.locations import decode_universal_address


def sample_discovery() -> Discovery:
    row = Discovery(
        id=123,
        approved_from_batch_id="batch",
        contributor="PJ",
        save_name="Flower-Kin",
        discovery_type="Animal",
        ua="0x1",
        vp0="0x2",
        vp1="0x3",
        vp2="0x4",
        vp3="0x5",
        vp4="",
        message_id="message",
        owner="PJ",
        platform="ST",
        record_hash="hash",
        raw_record={},
        public_attribution=True,
        display_name="",
        galaxy_number=42,
        galaxy_name="Xobeurindj",
        portal_glyphs="0123456789AB",
        location_status="verified",
        projector_status="verified",
        image_status="needed",
        catalog_note="",
    )
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = row.created_at
    return row


def test_wc_id_and_catalog_serialization():
    row = sample_discovery()
    assert wc_id(row) == "WC-A-000123"
    payload = serialize_discovery(row, detail=True)
    assert payload["has_location"] is True
    assert payload["portal_glyphs"] == "0123456789AB"


def test_verification_normalizes_glyphs():
    payload = LocationVerificationPayload(
        discovery_id=1,
        contributor="PJ",
        galaxy_number=1,
        portal_glyphs="01 23-45 67 89 ab",
    )
    assert payload.portal_glyphs == "0123456789AB"


def test_catalog_update_accepts_admin_actor():
    update = CatalogUpdate(actor="PJ", display_name="Long-neck fauna")
    assert update.actor == "PJ"


def test_private_attribution_masks_public_name():
    row = sample_discovery()
    row.public_attribution = False
    payload = serialize_discovery(row, detail=True)
    assert payload["contributor"] == "Anonymous Contributor"
    assert payload["save_name"] == ""
    assert payload["public_attribution"] is False


def test_confirmed_ua_decoding_vector():
    decoded = decode_universal_address("0x208BFF11112111")
    assert decoded is not None
    assert decoded["portal_glyphs"] == "208B11112111"
    assert decoded["reality_index"] == 255
    assert decoded["galaxy_number"] == 256
    assert decoded["galaxy_name"] == "Odyalutai"


def test_padded_importer_ua_is_decoded():
    decoded = decode_universal_address("0x00208BFF11112111")
    assert decoded is not None
    assert decoded["ua_normalized"] == "208BFF11112111"
    assert decoded["portal_glyphs"] == "208B11112111"


def test_unverified_record_exposes_ua_derived_travel_address():
    row = sample_discovery()
    row.ua = "0x00208BFF11112111"
    row.galaxy_number = None
    row.galaxy_name = ""
    row.portal_glyphs = ""
    row.location_status = "unverified"
    payload = serialize_discovery(row, detail=True)
    assert payload["has_location"] is False
    assert payload["has_travel_address"] is True
    assert payload["travel_status"] == "derived"
    assert payload["location_source"] == "ua_confirmed_v1"
    assert payload["portal_glyphs"] == "208B11112111"
    assert payload["galaxy_number"] == 256
    assert payload["galaxy_name"] == "Odyalutai"


def test_confirmed_pet_match_selects_supported_fauna_archetype():
    row = sample_discovery()
    match = PetDiscoveryMatch(
        approved_from_batch_id=row.approved_from_batch_id,
        contributor="PJ",
        save_name="Flower-Kin",
        creature_id="TRICERATOPS",
        creature_type="",
        ua=row.ua,
        vp0=row.vp0,
        vp1=row.vp1,
        vp2=row.vp2,
        vp3=row.vp3,
        vp4=row.vp4,
        secondary_seed="",
        secondary_check="",
        message_id=row.message_id,
        record_hash="pet-hash",
        raw_record={},
        public_attribution=True,
    )
    assert discovery_match_key(row) == discovery_match_key(match)
    assert archetype_metadata(row, match) == {
        "archetype_key": "fauna.triceratops",
        "archetype_label": "Horned grazer",
        "archetype_source": "confirmed_pet_match",
    }


def test_unknown_or_nonfauna_record_uses_neutral_category_fallback():
    row = sample_discovery()
    row.discovery_type = "Flora"
    metadata = archetype_metadata(row)
    assert metadata["archetype_key"] == "flora.unknown"
    assert metadata["archetype_source"] == "category_fallback"
