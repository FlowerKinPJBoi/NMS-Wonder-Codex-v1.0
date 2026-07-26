from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..schemas import UserProfileUpdate
from ..services.accounts import (
    AuthIdentity,
    encrypt_friend_code,
    profile_for_identity,
    require_identity,
    serialize_profile,
)


router = APIRouter(tags=["accounts"])


@router.get("/auth/config")
def auth_config():
    settings = get_settings()
    return {
        "enabled": settings.accounts_ready,
        "supabase_url": settings.auth_supabase_url if settings.accounts_ready else "",
        "supabase_anon_key": settings.auth_supabase_anon_key if settings.accounts_ready else "",
        "providers": ["discord", "email"] if settings.accounts_ready else [],
    }


@router.get("/account/me")
def account_me(
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    return {"profile": serialize_profile(profile_for_identity(session, identity), include_private=True)}


@router.patch("/account/me")
def update_account(
    changes: UserProfileUpdate,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = profile_for_identity(session, identity)
    profile.contributor_name = changes.contributor_name
    profile.public_attribution = changes.public_attribution
    profile.platform = changes.platform
    profile.bot_connect_consent = changes.bot_connect_consent
    if changes.nms_friend_code is not None:
        profile.nms_friend_code_encrypted = (
            encrypt_friend_code(changes.nms_friend_code) if changes.nms_friend_code else ""
        )
        profile.friend_code_verified_at = None
    session.commit()
    session.refresh(profile)
    return {"profile": serialize_profile(profile, include_private=True)}
