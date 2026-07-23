from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import (
    AuditEvent,
    AssetSpecimen,
    CaptureSubmission,
    Discovery,
    LocationVerification,
    ImageContribution,
    PetDiscoveryMatch,
    SubmissionBatch,
    SubmissionIssue,
    SubmittedDiscovery,
    SubmittedPetMatch,
)
from ..schemas import CatalogUpdate, ImageReviewAction, ReviewAction, VerificationReviewAction
from ..services.catalog import serialize_discovery, wc_id
from ..services.bulk import insert_conflict_safe
from ..services.security import require_admin_key
from ..services.storage import delete_object, signed_review_url, verify_object

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


def _admin_discovery_payload(discovery: Discovery, *, detail: bool = False):
    payload = serialize_discovery(discovery, detail=detail)
    payload["contributor"] = discovery.contributor
    payload["save_name"] = discovery.save_name
    payload["public_attribution"] = discovery.public_attribution
    return payload


@router.get("/summary")
def admin_summary(session: Session = Depends(get_session)):
    return {
        "pending_captures": session.scalar(
            select(func.count()).select_from(CaptureSubmission).where(CaptureSubmission.status == "pending")
        ) or 0,
        "pending_batches": session.scalar(
            select(func.count()).select_from(SubmissionBatch).where(SubmissionBatch.status == "pending")
        ) or 0,
        "approved_batches": session.scalar(
            select(func.count()).select_from(SubmissionBatch).where(SubmissionBatch.status == "approved")
        ) or 0,
        "rejected_batches": session.scalar(
            select(func.count()).select_from(SubmissionBatch).where(SubmissionBatch.status == "rejected")
        ) or 0,
        "pending_discoveries": session.scalar(
            select(func.count()).select_from(SubmittedDiscovery).where(SubmittedDiscovery.review_status == "pending")
        ) or 0,
        "pending_pet_matches": session.scalar(
            select(func.count()).select_from(SubmittedPetMatch).where(SubmittedPetMatch.review_status == "pending")
        ) or 0,
        "published_discoveries": session.scalar(select(func.count()).select_from(Discovery)) or 0,
        "published_pet_matches": session.scalar(select(func.count()).select_from(PetDiscoveryMatch)) or 0,
        "pending_verifications": session.scalar(
            select(func.count()).select_from(LocationVerification).where(LocationVerification.status == "pending")
        ) or 0,
        "approved_verifications": session.scalar(
            select(func.count()).select_from(LocationVerification).where(LocationVerification.status == "approved")
        ) or 0,
        "verified_locations": session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.location_status == "verified")
        ) or 0,
        "images_needed": session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.image_status == "needed")
        ) or 0,
        "pending_images": session.scalar(
            select(func.count()).select_from(ImageContribution).where(ImageContribution.status == "pending")
        ) or 0,
        "pending_assets": session.scalar(
            select(func.count()).select_from(AssetSpecimen).where(AssetSpecimen.publication_state == "review")
        ) or 0,
        "published_assets": session.scalar(
            select(func.count()).select_from(AssetSpecimen).where(AssetSpecimen.publication_state == "published")
        ) or 0,
    }


def _capture_payload(row: CaptureSubmission) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "status": row.status,
        "contributor": row.contributor,
        "save_name": row.save_name,
        "platform": row.platform,
        "client_version": row.client_version,
        "public_attribution": row.public_attribution,
        "discovery_type": row.discovery_type,
        "ua": row.ua,
        "vp": [row.vp0, row.vp1, row.vp2, row.vp3, row.vp4],
        "message_id": row.message_id,
        "creature_id": row.creature_id,
        "creature_type": row.creature_type,
        "discovery": row.discovery_record,
        "image_role": row.image_role,
        "caption": row.caption,
        "original_filename": row.original_filename,
        "width": row.width,
        "height": row.height,
        "size_bytes": row.size_bytes,
        "reviewer_note": row.reviewer_note,
        "published_discovery_id": row.published_discovery_id,
    }


@router.get("/captures")
def list_captures(
    status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(CaptureSubmission)
        .where(CaptureSubmission.status == status)
        .order_by(CaptureSubmission.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": [_capture_payload(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/captures/{capture_id}")
def get_capture(capture_id: str, session: Session = Depends(get_session)):
    row = session.get(CaptureSubmission, capture_id)
    if not row:
        raise HTTPException(status_code=404, detail="Capture pair not found.")
    payload = _capture_payload(row)
    payload["preview_url"] = (
        f"/api/images/{row.id}/content"
        if row.status == "approved"
        else signed_review_url(row.object_key) if row.object_key else ""
    )
    if row.published_discovery_id:
        discovery = session.get(Discovery, row.published_discovery_id)
        payload["published_discovery"] = (
            _admin_discovery_payload(discovery, detail=True) if discovery else None
        )
    return {"capture": payload}


@router.post("/captures/{capture_id}/approve")
def approve_capture(
    capture_id: str,
    action: ImageReviewAction,
    session: Session = Depends(get_session),
):
    row = session.get(CaptureSubmission, capture_id)
    if not row:
        raise HTTPException(status_code=404, detail="Capture pair not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Capture pair is already {row.status}.")
    verify_object(row.object_key)

    discovery = session.scalar(select(Discovery).where(Discovery.record_hash == row.record_hash))
    created_discovery = discovery is None
    if discovery is None:
        discovery = Discovery(
            approved_from_batch_id=row.id,
            contributor=row.contributor,
            save_name=row.save_name or "Capture Companion",
            discovery_type=row.discovery_type,
            ua=row.ua,
            vp0=row.vp0,
            vp1=row.vp1,
            vp2=row.vp2,
            vp3=row.vp3,
            vp4=row.vp4,
            message_id=row.message_id,
            owner="",
            platform=row.platform,
            record_hash=row.record_hash,
            raw_record=row.discovery_record,
            public_attribution=row.public_attribution,
            display_name=row.discovery_record.get("CustomName", ""),
            projector_status="data_available" if row.message_id else "unverified",
            image_status="available",
        )
        session.add(discovery)
        session.flush()

    if action.approval_role == "primary":
        session.execute(
            update(ImageContribution)
            .where(
                ImageContribution.discovery_id == discovery.id,
                ImageContribution.status == "approved",
            )
            .values(is_primary=False)
        )
        is_primary = True
    else:
        current_primary = session.scalar(
            select(ImageContribution).where(
                ImageContribution.discovery_id == discovery.id,
                ImageContribution.status == "approved",
                ImageContribution.is_primary.is_(True),
            )
        )
        is_primary = current_primary is None
    # Capture pairs are already de-duplicated by normalized record + image hash.
    # Reuse the immutable capture UUID as the public image id so its approved
    # preview route stays stable even if the same bytes arrived another way.
    image = ImageContribution(
        id=row.id,
        discovery_id=discovery.id,
        contributor=row.contributor,
        image_role=row.image_role,
        caption=row.caption,
        permission_confirmed=True,
        status="approved",
        reviewed_at=datetime.now(timezone.utc),
        reviewer_note=action.note,
        object_key=row.object_key,
        public_url="",
        original_filename=row.original_filename,
        content_type=row.content_type,
        width=row.width,
        height=row.height,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        is_primary=is_primary,
        submitter_ip_hash=row.submitter_ip_hash,
        user_agent=row.user_agent,
        public_attribution=row.public_attribution,
    )
    session.add(image)

    discovery.image_status = "available"
    row.status = "approved"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    row.published_discovery_id = discovery.id
    session.add(AuditEvent(
        event_type="capture_pair_approved",
        actor=action.actor,
        batch_id=row.id,
        detail={
            "wc_id": wc_id(discovery),
            "created_discovery": created_discovery,
            "image_primary": is_primary,
            "note": action.note,
        },
    ))
    session.commit()
    return {
        "ok": True,
        "status": "approved",
        "discovery_id": discovery.id,
        "wc_id": wc_id(discovery),
        "created_discovery": created_discovery,
        "is_primary": is_primary,
    }


@router.post("/captures/{capture_id}/reject")
def reject_capture(
    capture_id: str,
    action: ImageReviewAction,
    session: Session = Depends(get_session),
):
    row = session.get(CaptureSubmission, capture_id)
    if not row:
        raise HTTPException(status_code=404, detail="Capture pair not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Capture pair is already {row.status}.")
    delete_object(row.object_key)
    row.object_key = ""
    row.status = "rejected"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    session.add(AuditEvent(
        event_type="capture_pair_rejected",
        actor=action.actor,
        batch_id=row.id,
        detail={"discovery_type": row.discovery_type, "note": action.note},
    ))
    session.commit()
    return {"ok": True, "status": "rejected"}


@router.get("/submissions")
def list_submissions(
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    batches = session.scalars(
        select(SubmissionBatch)
        .where(SubmissionBatch.status == status)
        .order_by(SubmissionBatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = []
    for batch in batches:
        items.append({
            "id": batch.id,
            "created_at": batch.created_at.isoformat(),
            "reviewed_at": batch.reviewed_at.isoformat() if batch.reviewed_at else None,
            "contributor": batch.contributor,
            "save_name": batch.save_name,
            "platform": batch.platform,
            "status": batch.status,
            "reviewer_note": batch.reviewer_note,
            "public_attribution": batch.public_attribution,
            "summary": batch.summary,
            "discovery_count": session.scalar(
                select(func.count()).select_from(SubmittedDiscovery).where(
                    SubmittedDiscovery.submission_batch_id == batch.id
                )
            ) or 0,
            "pet_match_count": session.scalar(
                select(func.count()).select_from(SubmittedPetMatch).where(
                    SubmittedPetMatch.submission_batch_id == batch.id
                )
            ) or 0,
            "issue_count": session.scalar(
                select(func.count()).select_from(SubmissionIssue).where(
                    SubmissionIssue.submission_batch_id == batch.id
                )
            ) or 0,
        })
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/submissions/{batch_id}")
def get_submission(batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(SubmissionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Submission not found.")

    discoveries = session.scalars(
        select(SubmittedDiscovery)
        .where(SubmittedDiscovery.submission_batch_id == batch_id)
        .limit(500)
    ).all()
    matches = session.scalars(
        select(SubmittedPetMatch)
        .where(SubmittedPetMatch.submission_batch_id == batch_id)
        .limit(500)
    ).all()
    issues = session.scalars(
        select(SubmissionIssue)
        .where(SubmissionIssue.submission_batch_id == batch_id)
        .limit(500)
    ).all()

    counts = {
        "discoveries": session.scalar(
            select(func.count()).select_from(SubmittedDiscovery).where(
                SubmittedDiscovery.submission_batch_id == batch_id
            )
        ) or 0,
        "pet_matches": session.scalar(
            select(func.count()).select_from(SubmittedPetMatch).where(
                SubmittedPetMatch.submission_batch_id == batch_id
            )
        ) or 0,
        "issues": session.scalar(
            select(func.count()).select_from(SubmissionIssue).where(
                SubmissionIssue.submission_batch_id == batch_id
            )
        ) or 0,
    }

    return {
        "batch": {
            "id": batch.id,
            "created_at": batch.created_at.isoformat(),
            "reviewed_at": batch.reviewed_at.isoformat() if batch.reviewed_at else None,
            "contributor": batch.contributor,
            "save_name": batch.save_name,
            "platform": batch.platform,
            "status": batch.status,
            "summary": batch.summary,
            "reviewer_note": batch.reviewer_note,
            "public_attribution": batch.public_attribution,
        },
        "counts": counts,
        "discoveries": [row.raw_record for row in discoveries],
        "pet_matches": [row.raw_record for row in matches],
        "issues": [row.raw_record for row in issues],
        "truncated_to_500_per_section": any(value > 500 for value in counts.values()),
    }


@router.post("/submissions/{batch_id}/approve")
def approve_submission(batch_id: str, action: ReviewAction, session: Session = Depends(get_session)):
    batch = session.get(SubmissionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if batch.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is already {batch.status}.")

    submitted_discoveries = session.scalars(
        select(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch_id)
    ).all()
    submitted_matches = session.scalars(
        select(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch_id)
    ).all()

    discovery_rows = [{
        "approved_from_batch_id": batch_id,
        "contributor": row.contributor,
        "save_name": row.save_name,
        "discovery_type": row.discovery_type,
        "ua": row.ua,
        "vp0": row.vp0,
        "vp1": row.vp1,
        "vp2": row.vp2,
        "vp3": row.vp3,
        "vp4": row.vp4,
        "message_id": row.message_id,
        "owner": row.owner,
        "platform": row.platform,
        "record_hash": row.record_hash,
        "raw_record": row.raw_record,
        "public_attribution": batch.public_attribution,
    } for row in submitted_discoveries]

    match_rows = [{
        "approved_from_batch_id": batch_id,
        "contributor": row.contributor,
        "save_name": row.save_name,
        "creature_id": row.creature_id,
        "creature_type": row.creature_type,
        "ua": row.ua,
        "vp0": row.vp0,
        "vp1": row.vp1,
        "vp2": row.vp2,
        "vp3": row.vp3,
        "vp4": row.vp4,
        "secondary_seed": row.secondary_seed,
        "secondary_check": row.secondary_check,
        "message_id": row.message_id,
        "record_hash": row.record_hash,
        "raw_record": row.raw_record,
        "public_attribution": batch.public_attribution,
    } for row in submitted_matches]

    discoveries_added = insert_conflict_safe(
        session,
        Discovery,
        discovery_rows,
        conflict_columns=["record_hash"],
    ) if discovery_rows else 0
    matches_added = insert_conflict_safe(
        session,
        PetDiscoveryMatch,
        match_rows,
        conflict_columns=["record_hash"],
    ) if match_rows else 0

    session.execute(
        update(SubmittedDiscovery)
        .where(SubmittedDiscovery.submission_batch_id == batch_id)
        .values(review_status="approved")
    )
    session.execute(
        update(SubmittedPetMatch)
        .where(SubmittedPetMatch.submission_batch_id == batch_id)
        .values(review_status="approved")
    )
    batch.status = "approved"
    batch.reviewed_at = datetime.now(timezone.utc)
    batch.reviewer_note = action.note
    session.add(AuditEvent(
        event_type="submission_approved",
        actor=action.actor,
        batch_id=batch_id,
        detail={
            "discoveries_added": discoveries_added,
            "matches_added": matches_added,
            "note": action.note,
            "public_attribution": batch.public_attribution,
        },
    ))
    session.commit()
    return {
        "ok": True,
        "status": "approved",
        "discoveries_added": discoveries_added,
        "pet_matches_added": matches_added,
        "duplicate_discoveries_skipped": len(discovery_rows) - discoveries_added,
        "duplicate_pet_matches_skipped": len(match_rows) - matches_added,
    }


@router.post("/submissions/{batch_id}/reject")
def reject_submission(batch_id: str, action: ReviewAction, session: Session = Depends(get_session)):
    batch = session.get(SubmissionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if batch.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is already {batch.status}.")

    session.execute(
        update(SubmittedDiscovery)
        .where(SubmittedDiscovery.submission_batch_id == batch_id)
        .values(review_status="rejected")
    )
    session.execute(
        update(SubmittedPetMatch)
        .where(SubmittedPetMatch.submission_batch_id == batch_id)
        .values(review_status="rejected")
    )
    batch.status = "rejected"
    batch.reviewed_at = datetime.now(timezone.utc)
    batch.reviewer_note = action.note
    session.add(AuditEvent(
        event_type="submission_rejected",
        actor=action.actor,
        batch_id=batch_id,
        detail={"note": action.note},
    ))
    session.commit()
    return {"ok": True, "status": "rejected"}


@router.get("/audit")
def audit_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(AuditEvent)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "items": [{
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "event_type": row.event_type,
            "actor": row.actor,
            "batch_id": row.batch_id,
            "detail": row.detail,
        } for row in rows],
        "limit": limit,
        "offset": offset,
    }

@router.get("/verifications")
def list_verifications(
    status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(LocationVerification)
        .where(LocationVerification.status == status)
        .order_by(LocationVerification.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = []
    for row in rows:
        discovery = session.get(Discovery, row.discovery_id)
        items.append({
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "status": row.status,
            "contributor": row.contributor,
            "public_attribution": row.public_attribution,
            "discovery_id": row.discovery_id,
            "wc_id": wc_id(discovery) if discovery else f"Record {row.discovery_id}",
            "display_name": discovery.display_name if discovery and discovery.display_name else "",
            "galaxy_number": row.galaxy_number,
            "galaxy_name": row.galaxy_name,
            "portal_glyphs": row.portal_glyphs,
            "reached_system": row.reached_system,
            "discovery_present": row.discovery_present,
            "projector_confirmed": row.projector_confirmed,
            "reviewer_note": row.reviewer_note,
        })
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/verifications/{verification_id}")
def get_verification(verification_id: str, session: Session = Depends(get_session)):
    row = session.get(LocationVerification, verification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Verification submission not found.")
    discovery = session.get(Discovery, row.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Linked Wonder record not found.")
    return {
        "verification": {
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "status": row.status,
            "contributor": row.contributor,
            "public_attribution": row.public_attribution,
            "galaxy_number": row.galaxy_number,
            "galaxy_name": row.galaxy_name,
            "portal_glyphs": row.portal_glyphs,
            "reached_system": row.reached_system,
            "discovery_present": row.discovery_present,
            "projector_confirmed": row.projector_confirmed,
            "notes": row.notes,
            "reviewer_note": row.reviewer_note,
        },
        "discovery": _admin_discovery_payload(discovery, detail=True),
    }


@router.post("/verifications/{verification_id}/approve")
def approve_verification(
    verification_id: str,
    action: VerificationReviewAction,
    session: Session = Depends(get_session),
):
    row = session.get(LocationVerification, verification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Verification submission not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Verification is already {row.status}.")
    discovery = session.get(Discovery, row.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Linked Wonder record not found.")

    location_applied = False
    if action.apply_location and row.galaxy_number and len(row.portal_glyphs) == 12:
        discovery.galaxy_number = row.galaxy_number
        discovery.galaxy_name = row.galaxy_name
        discovery.portal_glyphs = row.portal_glyphs
        # A present discovery at a reached system is the strongest location confirmation.
        discovery.location_status = "verified" if row.reached_system and row.discovery_present else "pending"
        location_applied = True
    elif discovery.location_status == "pending" and not discovery.portal_glyphs:
        discovery.location_status = "unverified"

    if row.projector_confirmed:
        discovery.projector_status = "verified"

    row.status = "approved"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    session.add(AuditEvent(
        event_type="verification_approved",
        actor=action.actor,
        batch_id=verification_id,
        detail={
            "discovery_id": discovery.id,
            "wc_id": wc_id(discovery),
            "location_applied": location_applied,
            "location_status": discovery.location_status,
            "note": action.note,
        },
    ))
    session.commit()
    return {
        "ok": True,
        "status": "approved",
        "location_applied": location_applied,
        "discovery": _admin_discovery_payload(discovery, detail=True),
    }


@router.post("/verifications/{verification_id}/reject")
def reject_verification(
    verification_id: str,
    action: VerificationReviewAction,
    session: Session = Depends(get_session),
):
    row = session.get(LocationVerification, verification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Verification submission not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Verification is already {row.status}.")
    discovery = session.get(Discovery, row.discovery_id)

    row.status = "rejected"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    if discovery and discovery.location_status == "pending" and not discovery.portal_glyphs:
        discovery.location_status = "unverified"
    session.add(AuditEvent(
        event_type="verification_rejected",
        actor=action.actor,
        batch_id=verification_id,
        detail={
            "discovery_id": row.discovery_id,
            "wc_id": wc_id(discovery) if discovery else None,
            "note": action.note,
        },
    ))
    session.commit()
    return {"ok": True, "status": "rejected"}


@router.get("/discoveries")
def admin_list_discoveries(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    query = select(Discovery)
    cleaned = " ".join(q.strip().split())
    if cleaned:
        pattern = f"%{cleaned}%"
        query = query.where(
            (Discovery.display_name.ilike(pattern))
            | (Discovery.contributor.ilike(pattern))
            | (Discovery.owner.ilike(pattern))
            | (Discovery.ua.ilike(pattern))
            | (Discovery.message_id.ilike(pattern))
            | (Discovery.galaxy_name.ilike(pattern))
        )
    rows = session.scalars(query.order_by(Discovery.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [_admin_discovery_payload(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/discoveries/{discovery_id}")
def admin_get_discovery(discovery_id: int, session: Session = Depends(get_session)):
    discovery = session.get(Discovery, discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")
    return _admin_discovery_payload(discovery, detail=True)


@router.patch("/discoveries/{discovery_id}")
def update_discovery_catalog(
    discovery_id: int,
    changes: CatalogUpdate,
    session: Session = Depends(get_session),
):
    discovery = session.get(Discovery, discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")

    values = changes.model_dump(exclude_unset=True)
    actor = values.pop("actor", "admin") or "admin"
    if values.get("location_status") == "verified":
        glyphs = values.get("portal_glyphs", discovery.portal_glyphs)
        galaxy_number = values.get("galaxy_number", discovery.galaxy_number)
        if not galaxy_number or len(glyphs or "") != 12:
            raise HTTPException(
                status_code=400,
                detail="A verified location requires a galaxy number and complete 12-glyph portal address.",
            )

    for key, value in values.items():
        setattr(discovery, key, value)

    session.add(AuditEvent(
        event_type="catalog_record_updated",
        actor=actor,
        batch_id=str(discovery.id),
        detail={"wc_id": wc_id(discovery), "fields": sorted(values.keys())},
    ))
    session.commit()
    session.refresh(discovery)
    return {"ok": True, "discovery": _admin_discovery_payload(discovery, detail=True)}



@router.get("/images")
def list_images(
    status: str = Query(default="pending"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(ImageContribution)
        .where(ImageContribution.status == status)
        .order_by(ImageContribution.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = []
    for row in rows:
        discovery = session.get(Discovery, row.discovery_id)
        items.append({
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "status": row.status,
            "contributor": row.contributor,
            "public_attribution": row.public_attribution,
            "discovery_id": row.discovery_id,
            "wc_id": wc_id(discovery) if discovery else f"Record {row.discovery_id}",
            "display_name": discovery.display_name if discovery and discovery.display_name else "",
            "image_role": row.image_role,
            "caption": row.caption,
            "width": row.width,
            "height": row.height,
            "size_bytes": row.size_bytes,
            "is_primary": row.is_primary,
            "public_url": f"/api/images/{row.id}/content" if row.status == "approved" else "",
        })
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/images/{image_id}")
def get_image(image_id: str, session: Session = Depends(get_session)):
    row = session.get(ImageContribution, image_id)
    if not row:
        raise HTTPException(status_code=404, detail="Image submission not found.")
    discovery = session.get(Discovery, row.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Linked Wonder record not found.")
    preview_url = f"/api/images/{row.id}/content" if row.status == "approved" else signed_review_url(row.object_key)
    return {
        "image": {
            "id": row.id,
            "created_at": row.created_at.isoformat(),
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "status": row.status,
            "contributor": row.contributor,
            "public_attribution": row.public_attribution,
            "image_role": row.image_role,
            "caption": row.caption,
            "reviewer_note": row.reviewer_note,
            "original_filename": row.original_filename,
            "content_type": row.content_type,
            "width": row.width,
            "height": row.height,
            "size_bytes": row.size_bytes,
            "is_primary": row.is_primary,
            "preview_url": preview_url,
            "public_url": f"/api/images/{row.id}/content" if row.status == "approved" else "",
            "cdn_url": row.public_url,
        },
        "discovery": _admin_discovery_payload(discovery, detail=True),
    }


@router.post("/images/{image_id}/approve")
def approve_image(image_id: str, action: ImageReviewAction, session: Session = Depends(get_session)):
    row = session.get(ImageContribution, image_id)
    if not row:
        raise HTTPException(status_code=404, detail="Image submission not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Image is already {row.status}.")
    discovery = session.get(Discovery, row.discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Linked Wonder record not found.")

    # Keep approved files private. Public delivery is gated by the database
    # status and served through /api/images/{id}/content.
    verify_object(row.object_key)
    public_url = ""
    if action.approval_role == "primary":
        session.execute(
            update(ImageContribution)
            .where(ImageContribution.discovery_id == discovery.id, ImageContribution.status == "approved")
            .values(is_primary=False)
        )
        row.is_primary = True
    else:
        existing_primary = session.scalar(select(ImageContribution).where(
            ImageContribution.discovery_id == discovery.id,
            ImageContribution.status == "approved",
            ImageContribution.is_primary.is_(True),
        ))
        row.is_primary = existing_primary is None

    row.public_url = public_url
    row.status = "approved"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    discovery.image_status = "available"
    session.add(AuditEvent(
        event_type="image_approved",
        actor=action.actor,
        batch_id=row.id,
        detail={"wc_id": wc_id(discovery), "image_role": row.image_role, "primary": row.is_primary, "note": action.note},
    ))
    session.commit()
    return {
        "ok": True,
        "status": "approved",
        "public_url": f"/api/images/{row.id}/content",
        "cdn_url": public_url,
        "is_primary": row.is_primary,
    }


@router.post("/images/{image_id}/reject")
def reject_image(image_id: str, action: ImageReviewAction, session: Session = Depends(get_session)):
    row = session.get(ImageContribution, image_id)
    if not row:
        raise HTTPException(status_code=404, detail="Image submission not found.")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"Image is already {row.status}.")
    discovery = session.get(Discovery, row.discovery_id)
    delete_object(row.object_key)
    row.object_key = ""
    row.status = "rejected"
    row.reviewed_at = datetime.now(timezone.utc)
    row.reviewer_note = action.note
    remaining = session.scalar(select(func.count()).select_from(ImageContribution).where(
        ImageContribution.discovery_id == row.discovery_id,
        ImageContribution.status.in_(["pending", "approved"]),
        ImageContribution.id != row.id,
    )) or 0
    if discovery and remaining == 0:
        discovery.image_status = "needed"
    session.add(AuditEvent(
        event_type="image_rejected",
        actor=action.actor,
        batch_id=row.id,
        detail={"wc_id": wc_id(discovery) if discovery else str(row.discovery_id), "note": action.note},
    ))
    session.commit()
    return {"ok": True, "status": "rejected"}
