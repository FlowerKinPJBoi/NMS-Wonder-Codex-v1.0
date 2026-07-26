from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.config import get_settings
from app.schemas import UserAccessUpdate, UserProfileUpdate
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
