from datetime import datetime, timezone

from app.models import Discovery, PetDiscoveryMatch
from app.config import Settings
from app.schemas import CatalogUpdate, LocationVerificationPayload
from app.services.archetypes import (
    archetype_metadata,
    build_exact_match_index,
    build_vp1_family_index,
    discovery_match_key,
    family_vp1s,
)
from app.services.catalog import is_publicly_listed_discovery_type, serialize_discovery, wc_id
from app.services.locations import decode_portal_coordinates, decode_universal_address


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


def test_solar_systems_are_retained_but_not_publicly_listed():
    assert is_publicly_listed_discovery_type("Animal") is True
    assert is_publicly_listed_discovery_type("SolarSystem") is False


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


def test_named_admin_keys_parse_from_environment_json():
    settings = Settings(admin_api_keys='{"PJ":"pj-key","Boots":"boots-key"}')
    assert settings.admin_api_keys == {"PJ": "pj-key", "Boots": "boots-key"}


def test_named_tester_keys_accept_individual_values():
    settings = Settings(
        tester_api_key_menomoo="meno-key",
        tester_api_key_floppydonkey="floppy-key",
        tester_api_key_monketsu="monk-key",
        tester_api_key_readyfireaim="ready-key",
        tester_api_key_visceral="visceral-key",
        tester_api_key_ekimo="ekimo-key",
    )
    assert settings.tester_api_keys["Menomoo"] == "meno-key"
    assert settings.tester_api_keys["FloppyDonkey"] == "floppy-key"
    assert settings.tester_api_keys["Monketsu"] == "monk-key"
    assert settings.tester_api_keys["ReadyFireAim"] == "ready-key"
    assert settings.tester_api_keys["Visceral"] == "visceral-key"
    assert settings.tester_api_keys["Ekimo"] == "ekimo-key"


def test_named_admin_keys_accept_individual_environment_values(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY_PJ", "pj-key")
    monkeypatch.setenv("ADMIN_API_KEY_BOOTS", "boots-key")
    settings = Settings()
    assert settings.admin_api_key_pj == "pj-key"
    assert settings.admin_api_key_boots == "boots-key"


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


def test_portal_coordinates_match_verified_pegasus_vectors():
    current = decode_portal_coordinates("008B11112111")
    assert current is not None
    assert (current["x"], current["y"], current["z"]) == (273, 17, 274)
    assert current["solar_system_index"] == 139

    destination = decode_portal_coordinates("4079FB2FD9DD")
    assert destination is not None
    assert (destination["x"], destination["y"], destination["z"]) == (-1571, -5, 765)
    assert destination["planet_index"] == 4
    assert destination["solar_system_index"] == 121


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


def sample_pet_match(row: Discovery, creature_id: str = "TRICERATOPS", creature_type: str = "Prey") -> PetDiscoveryMatch:
    return PetDiscoveryMatch(
        approved_from_batch_id=row.approved_from_batch_id,
        contributor="PJ",
        save_name="Flower-Kin",
        creature_id=creature_id,
        creature_type=creature_type,
        ua=row.ua,
        vp0=row.vp0,
        vp1=row.vp1,
        vp2=row.vp2,
        vp3=row.vp3,
        vp4=row.vp4,
        secondary_seed="",
        secondary_check="",
        message_id=row.message_id,
        record_hash=f"pet-hash-{creature_id}",
        raw_record={},
        public_attribution=True,
    )


def test_confirmed_pet_match_selects_supported_fauna_archetype():
    row = sample_discovery()
    match = sample_pet_match(row)
    vp1_index = build_vp1_family_index([match])
    assert discovery_match_key(row) == discovery_match_key(match)
    assert build_exact_match_index([match])[discovery_match_key(row)] is match
    metadata = archetype_metadata(row, match, vp1_index[row.vp1])
    assert metadata["archetype_key"] == "fauna.triceratops"
    assert metadata["archetype_source"] == "confirmed_pet_match"
    assert metadata["fauna_family_id"] == "TRICERATOPS"
    assert metadata["fauna_family_label"] == "Triceratops"
    assert metadata["fauna_behavior"] == "Prey"
    assert metadata["fauna_identity_source"] == "exact_pet_match"


def test_all_projector_capture_families_select_their_supported_archetypes():
    expected = {
        "ANTELOPE": "fauna.antelope",
        "BLOB": "fauna.blob",
        "BONECOW": "fauna.bonecow",
        "CAT": "fauna.cat",
        "COW": "fauna.cow",
        "FLOATSPIDER": "fauna.floatspider",
        "FLYINGBEETLE": "fauna.flyingbeetle",
        "GRUNT": "fauna.grunt",
        "HERMITCRAB": "fauna.hermitcrab",
        "LARGEBUTTERFLY": "fauna.largebutterfly",
        "PROTOFLYER": "fauna.protoflyer",
        "ROBOTANTELOPE": "fauna.robotantelope",
        "SIXLEGCOW": "fauna.sixlegcow",
        "SPIDER": "fauna.spider",
        "STRIDER": "fauna.strider",
        "TREX": "fauna.trex",
        "TRICERATOPS": "fauna.triceratops",
        "TWOLEGANTELOPE": "fauna.twolegantelope",
        "WALKINGBUILDING": "fauna.walkingbuilding",
        "WEIRDFLOAT": "fauna.weirdfloat",
    }
    row = sample_discovery()

    for creature_id, archetype_key in expected.items():
        metadata = archetype_metadata(row, sample_pet_match(row, creature_id))
        assert metadata["archetype_key"] == archetype_key
        assert metadata["fauna_family_id"] == creature_id
        assert metadata["archetype_source"] == "confirmed_pet_match"


def test_unambiguous_vp1_mapping_labels_related_discoveries_without_copying_behavior():
    row = sample_discovery()
    match = sample_pet_match(row, "TREX", "Predator")
    vp1_family = build_vp1_family_index([match])[row.vp1]
    metadata = archetype_metadata(row, None, vp1_family)
    assert metadata["archetype_key"] == "fauna.trex"
    assert metadata["fauna_family_label"] == "T-Rex"
    assert metadata["fauna_behavior"] == ""
    assert metadata["fauna_identity_source"] == "confirmed_vp1_mapping"


def test_conflicting_vp1_family_evidence_is_not_inferred():
    row = sample_discovery()
    match_a = sample_pet_match(row, "CAT", "Passive")
    match_b = sample_pet_match(row, "TREX", "Predator")
    assert row.vp1 not in build_vp1_family_index([match_a, match_b])


def test_family_search_accepts_friendly_and_technical_names():
    index = {
        "0xA": {"creature_id": "TREX", "family_label": "T-Rex", "evidence_count": 1},
        "0xB": {"creature_id": "FLOATSPIDER", "family_label": "Float Spider", "evidence_count": 1},
    }
    assert family_vp1s(index, "T-Rex", exact=True) == ["0xA"]
    assert family_vp1s(index, "float spider", exact=True) == ["0xB"]
    assert family_vp1s(index, "spider", exact=False) == ["0xB"]


def test_unknown_or_nonfauna_record_uses_neutral_category_fallback():
    row = sample_discovery()
    row.discovery_type = "Flora"
    metadata = archetype_metadata(row)
    assert metadata["archetype_key"] == "flora.unknown"
    assert metadata["archetype_source"] == "category_fallback"
    assert metadata["fauna_family_id"] == ""
