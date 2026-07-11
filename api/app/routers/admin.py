from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import (
    AuditEvent,
    Discovery,
    PetDiscoveryMatch,
    SubmissionBatch,
    SubmissionIssue,
    SubmittedDiscovery,
    SubmittedPetMatch,
)
from ..schemas import ReviewAction
from ..services.security import require_admin_key

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


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
            "contributor": batch.contributor,
            "save_name": batch.save_name,
            "platform": batch.platform,
            "status": batch.status,
            "summary": batch.summary,
            "discovery_count": session.scalar(select(func.count()).select_from(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch.id)) or 0,
            "pet_match_count": session.scalar(select(func.count()).select_from(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch.id)) or 0,
            "issue_count": session.scalar(select(func.count()).select_from(SubmissionIssue).where(SubmissionIssue.submission_batch_id == batch.id)) or 0,
        })
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/submissions/{batch_id}")
def get_submission(batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(SubmissionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Submission not found.")
    discoveries = session.scalars(select(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch_id).limit(500)).all()
    matches = session.scalars(select(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch_id).limit(500)).all()
    issues = session.scalars(select(SubmissionIssue).where(SubmissionIssue.submission_batch_id == batch_id).limit(500)).all()
    return {
        "batch": {
            "id": batch.id,
            "created_at": batch.created_at.isoformat(),
            "contributor": batch.contributor,
            "save_name": batch.save_name,
            "platform": batch.platform,
            "status": batch.status,
            "summary": batch.summary,
            "reviewer_note": batch.reviewer_note,
        },
        "discoveries": [row.raw_record for row in discoveries],
        "pet_matches": [row.raw_record for row in matches],
        "issues": [row.raw_record for row in issues],
        "truncated_to_500_per_section": True,
    }


@router.post("/submissions/{batch_id}/approve")
def approve_submission(batch_id: str, action: ReviewAction, session: Session = Depends(get_session)):
    batch = session.get(SubmissionBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Submission not found.")
    if batch.status != "pending":
        raise HTTPException(status_code=409, detail=f"Submission is already {batch.status}.")

    submitted_discoveries = session.scalars(select(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch_id)).all()
    submitted_matches = session.scalars(select(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch_id)).all()

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
    } for row in submitted_matches]

    discoveries_added = 0
    matches_added = 0
    if discovery_rows:
        result = session.execute(
            insert(Discovery).values(discovery_rows)
            .on_conflict_do_nothing(index_elements=["record_hash"])
            .returning(Discovery.id)
        )
        discoveries_added = len(result.scalars().all())
    if match_rows:
        result = session.execute(
            insert(PetDiscoveryMatch).values(match_rows)
            .on_conflict_do_nothing(index_elements=["record_hash"])
            .returning(PetDiscoveryMatch.id)
        )
        matches_added = len(result.scalars().all())

    session.execute(update(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch_id).values(review_status="approved"))
    session.execute(update(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch_id).values(review_status="approved"))
    batch.status = "approved"
    batch.reviewed_at = datetime.now(timezone.utc)
    batch.reviewer_note = action.note
    session.add(AuditEvent(event_type="submission_approved", actor=action.actor, batch_id=batch_id, detail={
        "discoveries_added": discoveries_added,
        "matches_added": matches_added,
        "note": action.note,
    }))
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
    session.execute(update(SubmittedDiscovery).where(SubmittedDiscovery.submission_batch_id == batch_id).values(review_status="rejected"))
    session.execute(update(SubmittedPetMatch).where(SubmittedPetMatch.submission_batch_id == batch_id).values(review_status="rejected"))
    batch.status = "rejected"
    batch.reviewed_at = datetime.now(timezone.utc)
    batch.reviewer_note = action.note
    session.add(AuditEvent(event_type="submission_rejected", actor=action.actor, batch_id=batch_id, detail={"note": action.note}))
    session.commit()
    return {"ok": True, "status": "rejected"}
