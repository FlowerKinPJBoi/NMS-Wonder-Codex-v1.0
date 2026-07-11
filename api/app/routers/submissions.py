from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import check_database, get_session
from ..models import SubmissionBatch, SubmissionIssue, SubmittedDiscovery, SubmittedPetMatch
from ..schemas import SubmissionPayload
from ..services.hashing import canonical_hash, fingerprint
from ..services.rate_limit import enforce

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _clip(value: Any, length: int | None = None) -> str:
    text = str(value or "")
    return text[:length] if length else text


@router.post("")
def submit(payload: SubmissionPayload, request: Request, session: Session = Depends(get_session)):
    settings = get_settings()
    if payload.website:
        return {"ok": True, "queued": False}
    if not check_database():
        raise HTTPException(status_code=503, detail="Wonder Database is temporarily unavailable.")

    if len(payload.discoveries) > settings.max_discoveries_per_submission:
        raise HTTPException(status_code=413, detail="Too many discoveries in one submission.")
    if len(payload.matches) > settings.max_matches_per_submission:
        raise HTTPException(status_code=413, detail="Too many pet matches in one submission.")
    if len(payload.issues) > settings.max_issues_per_submission:
        raise HTTPException(status_code=413, detail="Too many issues in one submission.")

    contributor = payload.contributor
    if contributor.lower() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")

    ip_hash = enforce(request)
    batch_id = str(uuid.uuid4())
    source_fingerprint = fingerprint({
        "contributor": contributor,
        "save": payload.saveName,
        "platform": payload.platform,
        "summary": payload.summary,
        "discoveries": len(payload.discoveries),
        "matches": len(payload.matches),
    })

    batch = SubmissionBatch(
        id=batch_id,
        contributor=contributor,
        save_name=payload.saveName,
        platform=payload.platform,
        client_version=payload.version,
        status="pending",
        source_fingerprint=source_fingerprint,
        summary=payload.summary,
        submitter_ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent", "")[:1000],
    )
    session.add(batch)
    session.flush()

    discovery_rows = []
    for row in payload.discoveries:
        record_hash = canonical_hash(row, ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"])
        discovery_rows.append({
            "submission_batch_id": batch_id,
            "contributor": contributor,
            "save_name": payload.saveName,
            "discovery_type": _clip(row.get("DT"), 40),
            "ua": _clip(row.get("UA"), 32),
            "vp0": _clip(row.get("VP0"), 32),
            "vp1": _clip(row.get("VP1"), 32),
            "vp2": _clip(row.get("VP2"), 32),
            "vp3": _clip(row.get("VP3"), 32),
            "vp4": _clip(row.get("VP4"), 32),
            "message_id": _clip(row.get("MessageID")),
            "owner": _clip(row.get("Owner"), 160),
            "platform": _clip(row.get("Platform"), 40),
            "source_path": _clip(row.get("Path")),
            "record_hash": record_hash,
            "review_status": "pending",
            "raw_record": row,
        })

    match_rows = []
    for row in payload.matches:
        record_hash = canonical_hash(row, ["CreatureID", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"])
        match_rows.append({
            "submission_batch_id": batch_id,
            "contributor": contributor,
            "save_name": payload.saveName,
            "creature_id": _clip(row.get("CreatureID"), 120),
            "creature_type": _clip(row.get("CreatureType"), 120),
            "ua": _clip(row.get("UA"), 32),
            "vp0": _clip(row.get("VP0"), 32),
            "vp1": _clip(row.get("VP1"), 32),
            "vp2": _clip(row.get("VP2"), 32),
            "vp3": _clip(row.get("VP3"), 32),
            "vp4": _clip(row.get("VP4"), 32),
            "secondary_seed": _clip(row.get("SecondarySeed"), 32),
            "secondary_check": _clip(row.get("SecondaryCheck"), 40),
            "message_id": _clip(row.get("MessageID")),
            "pet_path": _clip(row.get("PetPath")),
            "discovery_path": _clip(row.get("DiscoveryPath")),
            "record_hash": record_hash,
            "review_status": "pending",
            "raw_record": row,
        })

    issue_rows = [{
        "submission_batch_id": batch_id,
        "contributor": contributor,
        "save_name": payload.saveName,
        "severity": _clip(row.get("Severity"), 30),
        "record_type": _clip(row.get("RecordType"), 50),
        "creature_id": _clip(row.get("CreatureID"), 120),
        "ua": _clip(row.get("UA"), 32),
        "issue": _clip(row.get("Issue")),
        "source_path": _clip(row.get("Path")),
        "raw_record": row,
    } for row in payload.issues]

    discovery_queued = 0
    match_queued = 0
    if discovery_rows:
        result = session.execute(
            insert(SubmittedDiscovery).values(discovery_rows)
            .on_conflict_do_nothing(index_elements=["record_hash"])
            .returning(SubmittedDiscovery.id)
        )
        discovery_queued = len(result.scalars().all())
    if match_rows:
        result = session.execute(
            insert(SubmittedPetMatch).values(match_rows)
            .on_conflict_do_nothing(index_elements=["record_hash"])
            .returning(SubmittedPetMatch.id)
        )
        match_queued = len(result.scalars().all())
    if issue_rows:
        session.execute(insert(SubmissionIssue).values(issue_rows))

    session.commit()
    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "submission_id": batch_id,
        "contributor": contributor,
        "save_name": payload.saveName,
        "received": {
            "discoveries": len(discovery_rows),
            "pet_matches": len(match_rows),
            "issues": len(issue_rows),
        },
        "queued_records": {
            "discoveries": discovery_queued,
            "pet_matches": match_queued,
        },
        "duplicates_skipped": {
            "discoveries": len(discovery_rows) - discovery_queued,
            "pet_matches": len(match_rows) - match_queued,
        },
    }


@router.get("/stats")
def submission_stats(session: Session = Depends(get_session)):
    return {
        "submission_batches": session.scalar(select(func.count()).select_from(SubmissionBatch)) or 0,
        "pending_batches": session.scalar(select(func.count()).select_from(SubmissionBatch).where(SubmissionBatch.status == "pending")) or 0,
        "submitted_discoveries": session.scalar(select(func.count()).select_from(SubmittedDiscovery)) or 0,
        "submitted_pet_matches": session.scalar(select(func.count()).select_from(SubmittedPetMatch)) or 0,
    }
