from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import NMSProfile, UserProfile


@dataclass(frozen=True)
class AuthIdentity:
    subject: str
    email: str
    metadata: dict[str, Any]
    provider: str


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient:
    base = get_settings().auth_supabase_url.rstrip("/")
    return jwt.PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.accounts_ready:
        raise HTTPException(status_code=503, detail="Wonder Codex accounts are not enabled yet.")
    issuer = f"{settings.auth_supabase_url.rstrip('/')}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        algorithm = str(header.get("alg", ""))
        if algorithm == "HS256" and settings.auth_jwt_secret.strip():
            key: Any = settings.auth_jwt_secret.strip()
        else:
            key = _jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            key,
            algorithms=["RS256", "ES256", "HS256"],
            audience="authenticated",
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Your sign-in session is invalid or expired.") from exc


def require_identity(authorization: str | None = Header(default=None)) -> AuthIdentity:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    claims = _decode_token(token.strip())
    metadata = claims.get("user_metadata") if isinstance(claims.get("user_metadata"), dict) else {}
    app_metadata = claims.get("app_metadata") if isinstance(claims.get("app_metadata"), dict) else {}
    return AuthIdentity(
        subject=str(claims["sub"]),
        email=str(claims.get("email", "")),
        metadata=metadata,
        provider=str(app_metadata.get("provider", "")),
    )


def profile_for_identity(session: Session, identity: AuthIdentity) -> UserProfile:
    profile = session.scalar(select(UserProfile).where(UserProfile.auth_subject == identity.subject))
    now = datetime.now(timezone.utc)
    if profile is None:
        custom_claims = identity.metadata.get("custom_claims")
        suggested_name = (
            custom_claims.get("global_name")
            if isinstance(custom_claims, dict)
            else ""
        ) or identity.metadata.get("full_name") or identity.metadata.get("user_name")
        suggested_name = " ".join(str(suggested_name or identity.email.split("@")[0] or "New Explorer").split())[:120]
        provider_id = None
        if identity.provider == "discord":
            provider_id = str(identity.metadata.get("provider_id", "")).strip() or None
        profile = UserProfile(
            id=str(uuid4()),
            auth_subject=identity.subject,
            contributor_name=suggested_name,
            discord_user_id=provider_id,
            last_sign_in_at=now,
        )
        session.add(profile)
    else:
        profile.last_sign_in_at = now
    session.commit()
    session.refresh(profile)
    if profile.account_status != "active":
        raise HTTPException(status_code=403, detail="This Wonder Codex account is suspended.")
    return profile


def _fernet() -> Fernet:
    key = get_settings().profile_encryption_key.strip()
    if not key:
        raise HTTPException(status_code=503, detail="Private profile storage is not configured yet.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=503, detail="Private profile storage is misconfigured.") from exc


def encrypt_friend_code(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_friend_code(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=500, detail="Private profile data could not be read.") from exc


def serialize_profile(profile: UserProfile, *, include_private: bool = False) -> dict[str, Any]:
    payload = {
        "id": profile.id,
        "contributor_name": profile.contributor_name,
        "public_attribution": profile.public_attribution,
        "platform": profile.platform,
        "access_tier": profile.access_tier,
        "account_status": profile.account_status,
        "discord_linked": bool(profile.discord_user_id),
        "has_nms_friend_code": bool(profile.nms_friend_code_encrypted),
        "bot_connect_consent": profile.bot_connect_consent,
        "friend_code_verified": bool(profile.friend_code_verified_at),
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "last_sign_in_at": profile.last_sign_in_at.isoformat() if profile.last_sign_in_at else None,
    }
    if include_private:
        payload["nms_friend_code"] = decrypt_friend_code(profile.nms_friend_code_encrypted)
    return payload


def serialize_nms_profile(profile: NMSProfile, *, include_private: bool = False) -> dict[str, Any]:
    payload = {
        "id": profile.id,
        "label": profile.label,
        "platform": profile.platform,
        "has_nms_friend_code": bool(profile.friend_code_encrypted),
        "bot_connect_consent": profile.bot_connect_consent,
        "friend_code_verified": bool(profile.friend_code_verified_at),
        "native_owner_uid": profile.native_owner_uid if profile.native_owner_verified_at else "",
        "native_owner_verified": bool(profile.native_owner_uid and profile.native_owner_verified_at),
        "is_default": profile.is_default,
        "active": profile.active,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
    if include_private:
        payload["nms_friend_code"] = decrypt_friend_code(profile.friend_code_encrypted)
    return payload


def nms_profiles_for_user(session: Session, user_profile_id: str, *, active_only: bool = False) -> list[NMSProfile]:
    query = select(NMSProfile).where(NMSProfile.user_profile_id == user_profile_id)
    if active_only:
        query = query.where(NMSProfile.active.is_(True))
    return list(session.scalars(query.order_by(NMSProfile.is_default.desc(), NMSProfile.created_at.asc())))


def selected_nms_profile(session: Session, user_profile_id: str, requested_id: str | None) -> NMSProfile:
    rows = nms_profiles_for_user(session, user_profile_id, active_only=True)
    if requested_id:
        chosen = next((row for row in rows if row.id == requested_id), None)
        if chosen is None:
            raise HTTPException(status_code=404, detail="That saved NMS profile is not available on this Passport.")
        return chosen
    if len(rows) == 1:
        return rows[0]
    defaults = [row for row in rows if row.is_default]
    if len(defaults) == 1 and len(rows) == 1:
        return defaults[0]
    if not rows:
        raise HTTPException(status_code=409, detail="Add an NMS profile to your Passport first.")
    raise HTTPException(status_code=409, detail="Choose which saved NMS profile you are using for this service.")
