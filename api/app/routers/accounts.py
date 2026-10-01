from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import NMSProfile
from ..schemas import NMSProfileCreate, NMSProfileUpdate, UserProfileUpdate
from ..services.accounts import (
    AuthIdentity,
    encrypt_friend_code,
    nms_profiles_for_user,
    profile_for_identity,
    require_identity,
    serialize_nms_profile,
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
    profile = profile_for_identity(session, identity)
    payload = serialize_profile(profile, include_private=True)
    payload["nms_profiles"] = [
        serialize_nms_profile(row, include_private=True)
        for row in nms_profiles_for_user(session, profile.id)
    ]
    return {"profile": payload}


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


@router.get("/account/nms-profiles")
def list_nms_profiles(
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = profile_for_identity(session, identity)
    return {
        "profiles": [
            serialize_nms_profile(row, include_private=True)
            for row in nms_profiles_for_user(session, profile.id)
        ]
    }


@router.post("/account/nms-profiles", status_code=201)
def create_nms_profile(
    changes: NMSProfileCreate,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = profile_for_identity(session, identity)
    existing = nms_profiles_for_user(session, profile.id)
    make_default = changes.is_default or not existing
    if make_default:
        session.execute(
            update(NMSProfile)
            .where(NMSProfile.user_profile_id == profile.id)
            .values(is_default=False)
        )
    row = NMSProfile(
        id=str(uuid4()),
        user_profile_id=profile.id,
        label=changes.label,
        platform=changes.platform,
        friend_code_encrypted=encrypt_friend_code(changes.nms_friend_code),
        bot_connect_consent=changes.bot_connect_consent,
        is_default=make_default,
        active=True,
    )
    session.add(row)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(status_code=409, detail="Use a unique label for each saved NMS profile.")
    session.refresh(row)
    return {"profile": serialize_nms_profile(row, include_private=True)}


@router.patch("/account/nms-profiles/{nms_profile_id}")
def update_nms_profile(
    nms_profile_id: str,
    changes: NMSProfileUpdate,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = profile_for_identity(session, identity)
    row = session.get(NMSProfile, nms_profile_id)
    if row is None or row.user_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Saved NMS profile not found.")
    supplied = changes.model_fields_set
    if "label" in supplied and changes.label is not None:
        row.label = changes.label
    if "platform" in supplied and changes.platform is not None:
        row.platform = changes.platform
    if "nms_friend_code" in supplied and changes.nms_friend_code is not None:
        row.friend_code_encrypted = encrypt_friend_code(changes.nms_friend_code) if changes.nms_friend_code else ""
        row.friend_code_verified_at = None
        row.native_owner_uid = ""
        row.native_owner_verified_at = None
    if "bot_connect_consent" in supplied and changes.bot_connect_consent is not None:
        row.bot_connect_consent = changes.bot_connect_consent
    if "active" in supplied and changes.active is not None:
        row.active = changes.active
    if changes.is_default is True:
        session.execute(
            update(NMSProfile)
            .where(NMSProfile.user_profile_id == profile.id, NMSProfile.id != row.id)
            .values(is_default=False)
        )
        row.is_default = True
        row.active = True
    elif changes.is_default is False and "is_default" in supplied:
        row.is_default = False
    session.add(row)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise HTTPException(status_code=409, detail="Use a unique label for each saved NMS profile.")
    session.refresh(row)
    return {"profile": serialize_nms_profile(row, include_private=True)}
