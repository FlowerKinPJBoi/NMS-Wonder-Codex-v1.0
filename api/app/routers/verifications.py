from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import check_database, get_session
from ..models import Discovery, LocationVerification
from ..schemas import LocationVerificationPayload
from ..services.catalog import wc_id
from ..services.rate_limit import enforce

router = APIRouter(prefix="/verifications", tags=["verifications"])


@router.post("")
def submit_verification(
    payload: LocationVerificationPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    if payload.website:
        return {"ok": True, "queued": False}
    if not check_database():
        raise HTTPException(status_code=503, detail="Wonder Database is temporarily unavailable.")

    contributor = payload.contributor
    if contributor.lower() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")

    discovery = session.get(Discovery, payload.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")

    ip_hash = enforce(request)
    verification_id = str(uuid.uuid4())
    verification = LocationVerification(
        id=verification_id,
        discovery_id=discovery.id,
        contributor=contributor,
        galaxy_number=payload.galaxy_number,
        galaxy_name=payload.galaxy_name,
        portal_glyphs=payload.portal_glyphs,
        reached_system=payload.reached_system,
        discovery_present=payload.discovery_present,
        projector_confirmed=payload.projector_confirmed,
        notes=payload.notes.strip(),
        status="pending",
        submitter_ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent", "")[:1000],
    )
    session.add(verification)

    if (
        discovery.location_status == "unverified"
        and payload.galaxy_number
        and len(payload.portal_glyphs) == 12
    ):
        discovery.location_status = "pending"

    session.commit()
    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "verification_id": verification_id,
        "discovery_id": discovery.id,
        "wc_id": wc_id(discovery),
        "contributor": contributor,
    }


@router.get("/{verification_id}")
def verification_status(verification_id: str, session: Session = Depends(get_session)):
    verification = session.get(LocationVerification, verification_id)
    if not verification:
        raise HTTPException(status_code=404, detail="Verification submission not found.")
    discovery = session.get(Discovery, verification.discovery_id)
    return {
        "id": verification.id,
        "status": verification.status,
        "created_at": verification.created_at.isoformat(),
        "reviewed_at": verification.reviewed_at.isoformat() if verification.reviewed_at else None,
        "wc_id": wc_id(discovery) if discovery else None,
        "reviewer_note": verification.reviewer_note,
    }
