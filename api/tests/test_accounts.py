from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import NMSProfileCreate, NMSProfileUpdate, UserAccessUpdate, UserProfileUpdate
from app.services.accounts import decrypt_friend_code, encrypt_friend_code


def test_profile_normalizes_contributor_and_friend_code():
    profile = UserProfileUpdate(
        contributor_name="  PJ   Boi ",
        platform="xbox",
        nms_friend_code="abcd efgh",
        bot_connect_consent=True,
    )
    assert profile.contributor_name == "PJ Boi"
    assert profile.nms_friend_code == "ABCDEFGH"


def test_access_tiers_are_bounded():
    assert UserAccessUpdate(access_tier="tester").access_tier == "tester"
    try:
        UserAccessUpdate(access_tier="owner")
    except ValidationError:
        pass
    else:
        raise AssertionError("Unexpected access tier was accepted.")


def test_friend_code_round_trip(monkeypatch):
    monkeypatch.setenv("PROFILE_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    get_settings.cache_clear()
    encrypted = encrypt_friend_code("ABCD-EFGH-IJKL")
    assert "ABCD-EFGH-IJKL" not in encrypted
    assert decrypt_friend_code(encrypted) == "ABCD-EFGH-IJKL"
    get_settings.cache_clear()

def test_nms_profile_normalizes_gog_label_and_friend_code():
    saved = NMSProfileCreate(
        label="  MSY   Nanobot Swarm  ",
        platform="gog",
        nms_friend_code="abcd efgh ijkl",
        bot_connect_consent=True,
        is_default=True,
    )
    assert saved.label == "MSY Nanobot Swarm"
    assert saved.platform == "gog"
    assert saved.nms_friend_code == "ABCDEFGHIJKL"
    assert saved.is_default is True


def test_nms_profile_update_allows_independent_account_state():
    update = NMSProfileUpdate(active=False, is_default=False, platform="steam")
    assert update.active is False
    assert update.is_default is False
    assert update.platform == "steam"
