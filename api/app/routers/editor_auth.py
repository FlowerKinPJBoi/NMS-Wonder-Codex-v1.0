from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import EditorAppConnection, UserProfile
from ..services.accounts import AuthIdentity, profile_for_identity, require_identity
from ..services.capture_auth import enforce_auth_rate, rate_for_request
from ..services.editor_auth import (
    POLL_SECONDS, SESSION_SECONDS, TOKEN_PREFIX, as_utc, connection_for_token, digest,
    new_connection, now_utc, require_editor_database, require_editor_profile, session_payload,
)
from .capture_auth import DeviceRequest, ApprovalRequest

router = APIRouter(prefix="/auth/editor", tags=["editor-passport"], dependencies=[Depends(require_editor_database)])


@router.post("/start")
def start(request: Request, session: Session = Depends(get_session)):
    if not get_settings().accounts_ready:
        raise HTTPException(503, "Passport sign-in is not configured on the site yet.")
    rate_for_request(session, request, "editor-start", 20)
    return new_connection(session)


@router.post("/approve")
def approve(body: ApprovalRequest, request: Request, identity: AuthIdentity = Depends(require_identity),
            session: Session = Depends(get_session)):
    rate_for_request(session, request, "editor-approve", 60)
    enforce_auth_rate(session, f"editor-approve-user:{identity.subject}", 30)
    profile = profile_for_identity(session, identity)
    if body.approved:
        require_editor_profile(profile)
        if not body.code_confirmed:
            raise HTTPException(400, "Confirm that this code matches Wonder Codex Editor on your computer.")
    result = session.execute(update(EditorAppConnection).where(
        EditorAppConnection.user_code_hash == digest(body.user_code), EditorAppConnection.status == "pending",
        EditorAppConnection.approval_expires_at > now_utc(),
    ).values(status="approved" if body.approved else "denied", profile_id=profile.id))
    session.commit()
    if result.rowcount != 1:
        raise HTTPException(400, "This Editor connection expired or was already used. Start sign-in again in the Editor.")
    return {"ok": True, "status": "approved" if body.approved else "denied"}


@router.post("/token")
def token(body: DeviceRequest, request: Request, session: Session = Depends(get_session)):
    rate_for_request(session, request, "editor-poll", 1800)
    connection = session.scalar(select(EditorAppConnection).where(
        EditorAppConnection.device_hash == digest(body.device_code),
    ).with_for_update())
    now = now_utc()
    if connection is None or as_utc(connection.approval_expires_at) <= now:
        raise HTTPException(400, "Editor connection expired. Sign in again.")
    if connection.status == "denied":
        raise HTTPException(403, "The Editor Passport connection was declined.")
    if connection.status not in {"pending", "approved"}:
        raise HTTPException(400, "Editor connection was cancelled or already used. Sign in again.")
    if connection.last_poll_at and (now - as_utc(connection.last_poll_at)).total_seconds() < POLL_SECONDS:
        session.commit()
        return {"status": "slow_down", "interval": POLL_SECONDS + 5}
    if connection.status == "pending":
        connection.last_poll_at = now
        session.commit()
        return {"status": "authorization_pending", "interval": POLL_SECONDS}
    profile = require_editor_profile(session.get(UserProfile, connection.profile_id))
    access_token = TOKEN_PREFIX + secrets.token_urlsafe(48)
    result = session.execute(update(EditorAppConnection).where(
        EditorAppConnection.device_hash == connection.device_hash, EditorAppConnection.status == "approved",
    ).values(status="active", token_hash=digest(access_token), token_expires_at=now + timedelta(seconds=SESSION_SECONDS)))
    session.commit()
    if result.rowcount != 1:
        raise HTTPException(400, "Editor connection was already used. Sign in again.")
    session.refresh(connection)
    return {"status": "authorized", "access_token": access_token, "token_type": "Bearer",
            **session_payload(connection, profile)}


@router.post("/cancel")
def cancel(body: DeviceRequest, request: Request, session: Session = Depends(get_session)):
    rate_for_request(session, request, "editor-cancel", 60)
    session.execute(update(EditorAppConnection).where(EditorAppConnection.device_hash == digest(body.device_code))
                    .values(status="cancelled", token_hash=None))
    session.commit()
    return {"ok": True}


@router.get("/session")
def current_session(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    return session_payload(*connection_for_token(session, authorization))


@router.post("/revoke")
def revoke(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not value.startswith(TOKEN_PREFIX) or len(value) != len(TOKEN_PREFIX) + 64:
        raise HTTPException(401, "An Editor Passport session is required.")
    session.execute(update(EditorAppConnection).where(EditorAppConnection.token_hash == digest(value))
                    .values(status="revoked", token_hash=None))
    session.commit()
    return {"ok": True}
