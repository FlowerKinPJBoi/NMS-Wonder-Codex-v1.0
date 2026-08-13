from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import AuditEvent, Discovery, PegasusDispatch, UserProfile
from ..schemas import PegasusDispatchCreate, PegasusWorkerClaim, PegasusWorkerUpdate
from ..services.accounts import AuthIdentity, profile_for_identity, require_identity
from ..services.pegasus import (
    PEGASUS_ACTIVE_STATUSES,
    PEGASUS_TERMINAL_STATUSES,
    destination_for,
    require_live_requester,
    serialize_dispatch,
    serialize_requester_dispatch,
    serialize_worker_dispatch,
)
from ..services.security import require_pegasus_worker_key


router = APIRouter(prefix="/pegasus", tags=["pegasus"])


def _requester_dispatch(session: Session, dispatch_id: str, profile: UserProfile) -> PegasusDispatch:
    dispatch = session.get(PegasusDispatch, dispatch_id)
    if not dispatch or dispatch.requester_profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Pegasus dispatch not found.")
    return dispatch


def _expire_stale_dispatches(session: Session, now: datetime) -> None:
    session.execute(
        update(PegasusDispatch)
        .where(
            PegasusDispatch.status.in_(PEGASUS_ACTIVE_STATUSES),
            PegasusDispatch.expires_at <= now,
        )
        .values(
            status="expired",
            phase="request_expired",
            status_message="This dispatch expired before departure. Request Pegasus again when ready.",
            completed_at=now,
            lease_expires_at=None,
        )
    )


@router.post("/dispatches", status_code=status.HTTP_201_CREATED)
def create_dispatch(
    request: PegasusDispatchCreate,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = require_live_requester(profile_for_identity(session, identity))
    discovery = session.get(Discovery, request.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")
    route = destination_for(discovery)
    now = datetime.now(timezone.utc)
    _expire_stale_dispatches(session, now)
    existing = session.scalar(
        select(PegasusDispatch)
        .where(
            PegasusDispatch.requester_profile_id == profile.id,
            PegasusDispatch.status.in_(PEGASUS_ACTIVE_STATUSES),
            PegasusDispatch.expires_at > now,
        )
        .order_by(PegasusDispatch.created_at.desc())
    )
    if existing:
        session.commit()
        return {"dispatch": serialize_requester_dispatch(existing), "reused": True}

    settings = get_settings()
    dispatch = PegasusDispatch(
        id=str(uuid4()),
        expires_at=now + timedelta(minutes=settings.pegasus_dispatch_ttl_minutes),
        requester_profile_id=profile.id,
        requester_name=profile.contributor_name,
        requester_tier=profile.access_tier,
        discovery_id=discovery.id,
        **route,
        status="queued",
        phase="awaiting_worker",
        status_message="WonderCodex received the route and is waiting for Pegasus.",
    )
    session.add(dispatch)
    session.add(AuditEvent(
        event_type="pegasus_dispatch_requested",
        actor=profile.contributor_name,
        batch_id=dispatch.id,
        detail={
            "requester_profile_id": profile.id,
            "requester_tier": profile.access_tier,
            "discovery_id": discovery.id,
            "wc_record_id": dispatch.wc_record_id,
        },
    ))
    session.commit()
    session.refresh(dispatch)
    return {"dispatch": serialize_requester_dispatch(dispatch), "reused": False}


@router.get("/dispatches/active")
def active_dispatch(
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = require_live_requester(profile_for_identity(session, identity))
    now = datetime.now(timezone.utc)
    _expire_stale_dispatches(session, now)
    dispatch = session.scalar(
        select(PegasusDispatch)
        .where(
            PegasusDispatch.requester_profile_id == profile.id,
            PegasusDispatch.status.in_(PEGASUS_ACTIVE_STATUSES),
            PegasusDispatch.expires_at > now,
        )
        .order_by(PegasusDispatch.created_at.desc())
    )
    session.commit()
    return {"dispatch": serialize_requester_dispatch(dispatch) if dispatch else None}


@router.get("/dispatches/{dispatch_id}")
def dispatch_status(
    dispatch_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = require_live_requester(profile_for_identity(session, identity))
    now = datetime.now(timezone.utc)
    _expire_stale_dispatches(session, now)
    dispatch = _requester_dispatch(session, dispatch_id, profile)
    session.commit()
    session.refresh(dispatch)
    return {"dispatch": serialize_requester_dispatch(dispatch)}


@router.post("/dispatches/{dispatch_id}/cancel")
def cancel_dispatch(
    dispatch_id: str,
    identity: AuthIdentity = Depends(require_identity),
    session: Session = Depends(get_session),
):
    profile = require_live_requester(profile_for_identity(session, identity))
    dispatch = _requester_dispatch(session, dispatch_id, profile)
    if dispatch.status in PEGASUS_TERMINAL_STATUSES:
        return {"dispatch": serialize_requester_dispatch(dispatch)}
    if dispatch.status != "queued":
        raise HTTPException(status_code=409, detail="Pegasus has already claimed this departure and cannot cancel it safely.")
    dispatch.status = "cancelled"
    dispatch.phase = "cancelled_by_requester"
    dispatch.status_message = "The requester cancelled this Pegasus dispatch."
    dispatch.completed_at = datetime.now(timezone.utc)
    dispatch.lease_expires_at = None
    session.add(AuditEvent(
        event_type="pegasus_dispatch_cancelled",
        actor=profile.contributor_name,
        batch_id=dispatch.id,
        detail={"wc_record_id": dispatch.wc_record_id},
    ))
    session.commit()
    session.refresh(dispatch)
    return {"dispatch": serialize_requester_dispatch(dispatch)}


@router.post("/worker/claim")
def claim_dispatch(
    claim: PegasusWorkerClaim,
    _worker_auth: str = Depends(require_pegasus_worker_key),
    session: Session = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    _expire_stale_dispatches(session, now)
    session.execute(
        update(PegasusDispatch)
        .where(
            PegasusDispatch.status.in_(PEGASUS_ACTIVE_STATUSES - {"queued"}),
            PegasusDispatch.lease_expires_at.is_not(None),
            PegasusDispatch.lease_expires_at <= now,
            PegasusDispatch.expires_at > now,
        )
        .values(
            status="queued",
            phase="worker_lease_expired",
            status_message="Pegasus lost contact while preparing this route; the dispatch was safely requeued.",
            worker_id="",
            lease_expires_at=None,
        )
    )
    dispatch = session.scalar(
        select(PegasusDispatch)
        .where(
            PegasusDispatch.status == "queued",
            PegasusDispatch.expires_at > now,
        )
        .order_by(PegasusDispatch.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    if not dispatch:
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    profile = session.get(UserProfile, dispatch.requester_profile_id)
    if (
        not profile
        or profile.account_status != "active"
        or profile.access_tier not in {"admin", "tester"}
        or not profile.bot_connect_consent
        or not profile.nms_friend_code_encrypted
    ):
        dispatch.status = "failed"
        dispatch.phase = "requester_profile_unavailable"
        dispatch.status_message = "Pegasus could not verify the requester's active Passport connection settings."
        dispatch.completed_at = now
        session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    settings = get_settings()
    dispatch.status = "claimed"
    dispatch.phase = "route_received"
    dispatch.status_message = "Pegasus claimed the route and is beginning preflight checks."
    dispatch.worker_id = claim.worker_id
    dispatch.claimed_at = now
    dispatch.expires_at = now + timedelta(minutes=settings.pegasus_active_dispatch_ttl_minutes)
    dispatch.lease_expires_at = now + timedelta(minutes=settings.pegasus_worker_lease_minutes)
    dispatch.attempt_count += 1
    session.commit()
    session.refresh(dispatch)
    return {"dispatch": serialize_worker_dispatch(dispatch, profile)}


@router.patch("/worker/dispatches/{dispatch_id}")
def update_dispatch(
    dispatch_id: str,
    progress: PegasusWorkerUpdate,
    _worker_auth: str = Depends(require_pegasus_worker_key),
    session: Session = Depends(get_session),
):
    dispatch = session.get(PegasusDispatch, dispatch_id)
    if not dispatch:
        raise HTTPException(status_code=404, detail="Pegasus dispatch not found.")
    if dispatch.status in PEGASUS_TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="This Pegasus dispatch is already closed.")
    if dispatch.worker_id != progress.worker_id:
        raise HTTPException(status_code=409, detail="This dispatch is leased to another Pegasus worker.")

    now = datetime.now(timezone.utc)
    if dispatch.lease_expires_at and dispatch.lease_expires_at <= now:
        raise HTTPException(status_code=409, detail="This Pegasus worker lease expired; the dispatch must be reclaimed.")
    dispatch.status = progress.status
    dispatch.phase = progress.phase or progress.status
    dispatch.status_message = progress.message or dispatch.status_message
    if progress.status in {"completed", "failed"}:
        dispatch.completed_at = now
        dispatch.lease_expires_at = None
    else:
        dispatch.lease_expires_at = now + timedelta(minutes=get_settings().pegasus_worker_lease_minutes)
    session.add(AuditEvent(
        event_type=f"pegasus_dispatch_{progress.status}",
        actor=progress.worker_id,
        batch_id=dispatch.id,
        detail={
            "wc_record_id": dispatch.wc_record_id,
            "phase": dispatch.phase,
            "attempt": dispatch.attempt_count,
        },
    ))
    session.commit()
    session.refresh(dispatch)
    return {"dispatch": serialize_dispatch(dispatch)}
