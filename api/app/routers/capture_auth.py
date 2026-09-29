from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import CaptureAppConnection, UserProfile
from ..services.accounts import AuthIdentity, profile_for_identity, require_identity
from ..services.capture_auth import (
    POLL_SECONDS, SESSION_SECONDS, TOKEN_PREFIX, as_utc, cleanup_connections,
    connection_for_token, digest, enforce_auth_rate, new_connection, now_utc,
    rate_for_request, require_capture_profile, session_payload,
)

router = APIRouter(prefix="/auth/capture", tags=["capture-passport"])


class DeviceRequest(BaseModel):
    device_code: str = Field(min_length=64, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ApprovalRequest(BaseModel):
    user_code: str = Field(pattern=r"^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$")
    approved: bool
    code_confirmed: bool = False


@router.post("/start")
def start(request: Request, session: Session = Depends(get_session)):
    if not get_settings().accounts_ready:
        raise HTTPException(503, "Passport sign-in is not configured on the site yet.")
    rate_for_request(session, request, "start", 20)
    cleanup_connections(session)
    return new_connection(session)


@router.post("/approve")
def approve(body: ApprovalRequest, request: Request,
            identity: AuthIdentity = Depends(require_identity), session: Session = Depends(get_session)):
    rate_for_request(session, request, "approve", 60)
    enforce_auth_rate(session, f"approve-user:{identity.subject}", 30)
    profile = profile_for_identity(session, identity)
    if body.approved:
        require_capture_profile(profile)
        if not body.code_confirmed:
            raise HTTPException(400, "Confirm that this code matches Capture Companion on your computer.")
    result = session.execute(update(CaptureAppConnection).where(
        CaptureAppConnection.user_code_hash == digest(body.user_code),
        CaptureAppConnection.status == "pending", CaptureAppConnection.approval_expires_at > now_utc(),
    ).values(status="approved" if body.approved else "denied", profile_id=profile.id))
    session.commit()
    if result.rowcount != 1:
        raise HTTPException(400, "This connection request expired or was already used. Start sign-in again in Capture Companion.")
    return {"ok": True, "status": "approved" if body.approved else "denied"}


@router.post("/token")
def token(body: DeviceRequest, request: Request, session: Session = Depends(get_session)):
    rate_for_request(session, request, "poll", 1800)
    connection = session.scalar(select(CaptureAppConnection).where(
        CaptureAppConnection.device_hash == digest(body.device_code),
    ).with_for_update())
    now = now_utc()
    if connection is None or as_utc(connection.approval_expires_at) <= now:
        raise HTTPException(400, "Connection request expired. Sign in again.")
    if connection.status == "denied":
        raise HTTPException(403, "The Passport connection was declined.")
    if connection.status not in {"pending", "approved"}:
        raise HTTPException(400, "Connection request was cancelled or already used. Sign in again.")
    if connection.last_poll_at and (now - as_utc(connection.last_poll_at)).total_seconds() < POLL_SECONDS:
        session.commit()
        return {"status": "slow_down", "interval": POLL_SECONDS + 5}
    if connection.status == "pending":
        connection.last_poll_at = now
        session.commit()
        return {"status": "authorization_pending", "interval": POLL_SECONDS}
    profile = require_capture_profile(session.get(UserProfile, connection.profile_id))
    access_token = TOKEN_PREFIX + secrets.token_urlsafe(48)
    expires = now + timedelta(seconds=SESSION_SECONDS)
    result = session.execute(update(CaptureAppConnection).where(
        CaptureAppConnection.device_hash == connection.device_hash,
        CaptureAppConnection.status == "approved",
    ).values(status="active", token_hash=digest(access_token), token_expires_at=expires))
    session.commit()
    if result.rowcount != 1:
        raise HTTPException(400, "Connection request was already used. Sign in again.")
    session.refresh(connection)
    return {"status": "authorized", "access_token": access_token, "token_type": "Bearer",
            **session_payload(connection, profile)}


@router.post("/cancel")
def cancel(body: DeviceRequest, request: Request, session: Session = Depends(get_session)):
    rate_for_request(session, request, "cancel", 60)
    # Also revoke a token issued just as the desktop cancelled its pending poll.
    session.execute(update(CaptureAppConnection).where(
        CaptureAppConnection.device_hash == digest(body.device_code),
    ).values(status="cancelled", token_hash=None))
    session.commit()
    return {"ok": True}


@router.get("/session")
def current_session(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    connection, profile = connection_for_token(session, authorization)
    return session_payload(connection, profile)


@router.post("/revoke")
def revoke(authorization: str | None = Header(default=None), session: Session = Depends(get_session)):
    # Revocation remains possible even after a role change or suspension.
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not value.startswith(TOKEN_PREFIX) or len(value) > 160:
        raise HTTPException(401, "A Capture Companion session is required.")
    session.execute(update(CaptureAppConnection).where(
        CaptureAppConnection.token_hash == digest(value),
    ).values(status="revoked", token_hash=None))
    session.commit()
    return {"ok": True}
