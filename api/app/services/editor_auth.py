"""Passport approvals scoped only to the Editor's explicit contribution uploads."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import Header, HTTPException, Depends
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..database import check_database, get_session
from ..models import EditorAppConnection, UserProfile
from .capture_auth import APPROVAL_SECONDS, SESSION_SECONDS, POLL_SECONDS, as_utc, digest, now_utc

TOKEN_PREFIX = "wcedit_"
SCOPE = "import:submit"


def require_editor_database() -> None:
    if not check_database():
        raise HTTPException(503, "Editor contribution support is not ready on the site yet. Keep your local selection and retry later.")


def require_editor_profile(profile: UserProfile | None) -> UserProfile:
    if profile is None or profile.account_status != "active":
        raise HTTPException(403, "This Passport is unavailable or suspended.")
    if profile.access_tier not in {"tester", "admin"}:
        raise HTTPException(403, "Editor contributions currently require a Tester or Admin Passport. Ask PJ to enable Tester access.")
    return profile


def new_connection(session: Session) -> dict:
    now = now_utc()
    session.execute(delete(EditorAppConnection).where(
        EditorAppConnection.approval_expires_at < now,
        or_(EditorAppConnection.token_expires_at.is_(None), EditorAppConnection.token_expires_at < now),
    ))
    device_code = secrets.token_urlsafe(48)
    raw = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))
    user_code = "-".join(raw[index:index + 4] for index in range(0, 12, 4))
    session.add(EditorAppConnection(device_hash=digest(device_code), user_code_hash=digest(user_code),
                                   created_at=now, approval_expires_at=now + timedelta(seconds=APPROVAL_SECONDS),
                                   status="pending"))
    session.commit()
    return {"device_code": device_code, "user_code": user_code, "expires_in": APPROVAL_SECONDS,
            "interval": POLL_SECONDS, "verification_uri": "https://wondercodex.com/account.html",
            "verification_uri_complete": f"https://wondercodex.com/account.html?editor={user_code}"}


def connection_for_token(session: Session, authorization: str | None) -> tuple[EditorAppConnection, UserProfile]:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token.startswith(TOKEN_PREFIX) or len(token) != len(TOKEN_PREFIX) + 64:
        raise HTTPException(401, "Sign in with Passport in Wonder Codex Editor.")
    connection = session.scalar(select(EditorAppConnection).where(
        EditorAppConnection.token_hash == digest(token), EditorAppConnection.status == "active",
    ))
    if connection is None or connection.token_expires_at is None or as_utc(connection.token_expires_at) <= now_utc():
        raise HTTPException(401, "Your Editor Passport session expired. Sign in again; your local selection is unchanged.")
    return connection, require_editor_profile(session.get(UserProfile, connection.profile_id))


def require_editor_submitter(authorization: str | None = Header(default=None),
                             session: Session = Depends(get_session)) -> UserProfile:
    # Intentionally no operator-key or Capture-session fallback.
    require_editor_database()
    return connection_for_token(session, authorization)[1]


def session_payload(connection: EditorAppConnection, profile: UserProfile) -> dict:
    return {"contributor_name": profile.contributor_name, "public_attribution": profile.public_attribution,
            "access_tier": profile.access_tier, "scopes": [SCOPE],
            "expires_at": as_utc(connection.token_expires_at).isoformat()}
