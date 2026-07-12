from datetime import datetime, timezone

from app.models import Discovery
from app.schemas import CatalogUpdate, LocationVerificationPayload
from app.services.catalog import serialize_discovery, wc_id


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
