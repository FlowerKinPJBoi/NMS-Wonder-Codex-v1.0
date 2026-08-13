from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.models import Discovery, UserProfile
from app.schemas import PegasusDispatchCreate, PegasusWorkerClaim, PegasusWorkerUpdate
from app.services.pegasus import destination_for, require_live_requester
from app.services.security import require_pegasus_worker_key


def profile(*, tier: str = "tester", consent: bool = True, friend_code: str = "encrypted") -> UserProfile:
    return UserProfile(
        id="profile-1",
        auth_subject="subject-1",
        contributor_name="PJ",
        access_tier=tier,
        account_status="active",
        nms_friend_code_encrypted=friend_code,
        bot_connect_consent=consent,
    )


def discovery() -> Discovery:
    row = Discovery(
        id=3084,
        approved_from_batch_id="batch",
        contributor="PJ",
        save_name="Flower-Kin",
        discovery_type="Animal",
        ua="0x1081A9FC250959",
        vp0="",
        vp1="",
        vp2="",
        vp3="",
        vp4="",
        message_id="message",
        owner="PJ",
        platform="Xbox",
        record_hash="hash",
        raw_record={},
        display_name="Ezdaranit test wonder",
        galaxy_number=170,
        galaxy_name="Ezdaranit",
        portal_glyphs="1081FC250959",
        location_status="verified",
        projector_status="verified",
        image_status="needed",
        catalog_note="",
    )
    row.created_at = datetime.now(timezone.utc)
    row.updated_at = row.created_at
    return row


def test_pegasus_requester_requires_role_consent_and_friend_code():
    assert require_live_requester(profile(tier="admin")).access_tier == "admin"
    assert require_live_requester(profile(tier="tester")).access_tier == "tester"
    for candidate in (
        profile(tier="regular"),
        profile(consent=False),
        profile(friend_code=""),
    ):
        with pytest.raises(HTTPException):
            require_live_requester(candidate)


def test_pegasus_destination_is_derived_from_catalog_record():
    route = destination_for(discovery())
    assert route["wc_record_id"] == "WC-A-003084"
    assert route["galaxy_number"] == 170
    assert route["portal_glyphs"] == "1081FC250959"
    assert route["universal_address"].startswith("0x")


def test_pegasus_worker_key_is_single_purpose(monkeypatch):
    monkeypatch.setenv("PEGASUS_WORKER_API_KEY", "worker-secret")
    get_settings.cache_clear()
    assert require_pegasus_worker_key("worker-secret") == "pegasus-worker"
    with pytest.raises(HTTPException) as error:
        require_pegasus_worker_key("wrong")
    assert error.value.status_code == 401
    get_settings.cache_clear()


def test_pegasus_request_and_worker_payloads_are_bounded():
    assert PegasusDispatchCreate(discovery_id=3084).discovery_id == 3084
    assert PegasusWorkerClaim(worker_id="  WonderCodex   Pegasus ").worker_id == "WonderCodex Pegasus"
    update = PegasusWorkerUpdate(
        worker_id="WonderCodex Pegasus",
        status="boarding",
        phase="session open",
        message="Ready for the tester.",
    )
    assert update.status == "boarding"
    assert update.phase == "session open"
