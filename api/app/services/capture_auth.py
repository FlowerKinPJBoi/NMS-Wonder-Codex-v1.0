from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import CaptureAppConnection, CaptureAuthRateWindow, UserProfile
from .rate_limit import client_ip
from .security import require_operator_key

APPROVAL_SECONDS = 600
SESSION_SECONDS = 8 * 60 * 60
POLL_SECONDS = 5
TOKEN_PREFIX = "wccap_"
SCOPE = "capture:submit"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def enforce_auth_rate(session: Session, key: str, limit: int) -> None:
    """Atomic database counters, shared by workers; retain only two windows."""
    window = int(now_utc().timestamp()) // 600
    session.execute(delete(CaptureAuthRateWindow).where(CaptureAuthRateWindow.window < window - 1))
    hashed = digest(f"capture-auth:{get_settings().ip_hash_salt}:{key}")
    insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    statement = insert(CaptureAuthRateWindow).values(key=hashed, window=window, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=["key", "window"],
        set_={"attempts": CaptureAuthRateWindow.attempts + 1},
    ).returning(CaptureAuthRateWindow.attempts)
    count = session.scalar(statement)
    session.commit()
    if count is not None and count > limit:
        raise HTTPException(429, "Too many connection attempts. Try again in ten minutes.",
                            headers={"Retry-After": "600"})


def rate_for_request(session: Session, request: Request, action: str, limit: int) -> None:
    enforce_auth_rate(session, f"{action}:{client_ip(request)}", limit)


def cleanup_connections(session: Session) -> None:
    now = now_utc()
    session.execute(delete(CaptureAppConnection).where(
        CaptureAppConnection.approval_expires_at < now,
        or_(CaptureAppConnection.token_expires_at.is_(None), CaptureAppConnection.token_expires_at < now),
    ))


def new_connection(session: Session) -> dict:
    now = now_utc()
    device_code = secrets.token_urlsafe(48)
    # 60 bits, unambiguous and readable. This code can approve but cannot poll.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(12))
    user_code = "-".join(raw[index:index + 4] for index in range(0, 12, 4))
    session.add(CaptureAppConnection(
        device_hash=digest(device_code), user_code_hash=digest(user_code), created_at=now,
        approval_expires_at=now + timedelta(seconds=APPROVAL_SECONDS), status="pending",
    ))
    session.commit()
    return {"device_code": device_code, "user_code": user_code,
            "expires_in": APPROVAL_SECONDS, "interval": POLL_SECONDS,
            "verification_uri": "https://wondercodex.com/account.html",
            "verification_uri_complete": f"https://wondercodex.com/account.html?capture={user_code}"}


def require_capture_profile(profile: UserProfile | None) -> UserProfile:
    if profile is None or profile.account_status != "active":
        raise HTTPException(403, "This Passport is unavailable or suspended.")
    if profile.access_tier not in {"tester", "admin"}:
        raise HTTPException(403, "Capture Companion currently requires a Tester or Admin Passport. Ask PJ to enable Tester access for this account.")
    return profile


def connection_for_token(session: Session, authorization: str | None) -> tuple[CaptureAppConnection, UserProfile]:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token.startswith(TOKEN_PREFIX) or len(token) > 160:
        raise HTTPException(401, "Sign in with Passport in Capture Companion.")
    connection = session.scalar(select(CaptureAppConnection).where(
        CaptureAppConnection.token_hash == digest(token), CaptureAppConnection.status == "active",
    ))
    if connection is None or connection.token_expires_at is None or as_utc(connection.token_expires_at) <= now_utc():
        raise HTTPException(401, "Your Capture Companion session has expired. Sign in again; your local pairs are unchanged.")
    profile = require_capture_profile(session.get(UserProfile, connection.profile_id))
    return connection, profile


def session_payload(connection: CaptureAppConnection, profile: UserProfile) -> dict:
    return {"contributor_name": profile.contributor_name,
            "public_attribution": profile.public_attribution,
            "access_tier": profile.access_tier, "scopes": [SCOPE],
            "expires_at": as_utc(connection.token_expires_at).isoformat()}


@dataclass(frozen=True)
class CaptureSubmitter:
    actor: str
    scopes: frozenset[str]
    profile_id: str | None = None
    public_attribution: bool = True


def require_capture_submitter(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
    x_admin_actor: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> CaptureSubmitter:
    # An invalid Bearer never falls back to a tester/admin key.
    if authorization is not None:
        _, profile = connection_for_token(session, authorization)
        return CaptureSubmitter(profile.contributor_name, frozenset({SCOPE}), profile.id, profile.public_attribution)
    # Preserve installed v0.3.7 clients during the coordinated rollout.
    operator = require_operator_key(x_admin_key, x_admin_actor)
    return CaptureSubmitter(operator.actor, operator.scopes)
