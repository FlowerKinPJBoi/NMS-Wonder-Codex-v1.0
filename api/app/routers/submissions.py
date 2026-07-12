from __future__ import annotations

import logging
import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import check_database, get_session
from ..models import SubmissionBatch, SubmissionIssue, SubmittedDiscovery, SubmittedPetMatch
from ..schemas import SubmissionPayload
from ..services.bulk import insert_conflict_safe, insert_plain
from ..services.hashing import canonical_hash, fingerprint
from ..services.rate_limit import enforce
from ..services.sanitization import clean_json, safe_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/submissions", tags=["submissions"])


def _clip(value: Any, length: int | None = None) -> str:
    text = safe_text(value)
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

    contributor = _clip(payload.contributor, 120)
    save_name = _clip(payload.saveName, 200)
    platform = _clip(payload.platform, 40)
    if contributor.lower() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")

    ip_hash = enforce(request)
    batch_id = str(uuid.uuid4())

    try:
        cleaned_summary = cast(dict[str, Any], clean_json(payload.summary))
        source_fingerprint = fingerprint({
            "contributor": contributor,
            "save": save_name,
            "platform": platform,
            "summary": cleaned_summary,
            "discoveries": len(payload.discoveries),
            "matches": len(payload.matches),
            "public_attribution": payload.publicAttribution,
        })

        batch = SubmissionBatch(
            id=batch_id,
            contributor=contributor,
            save_name=save_name,
            platform=platform,
            client_version=_clip(payload.version, 80),
            status="pending",
            source_fingerprint=source_fingerprint,
            summary=cleaned_summary,
            submitter_ip_hash=ip_hash,
            user_agent=_clip(request.headers.get("user-agent", ""), 1000),
            public_attribution=payload.publicAttribution,
        )
        session.add(batch)
        session.flush()

        discovery_rows: list[dict[str, Any]] = []
        for source_row in payload.discoveries:
            row = cast(dict[str, Any], clean_json(source_row))
            record_hash = canonical_hash(row, ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"])
            discovery_rows.append({
                "submission_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
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

        match_rows: list[dict[str, Any]] = []
        for source_row in payload.matches:
            row = cast(dict[str, Any], clean_json(source_row))
            record_hash = canonical_hash(row, ["CreatureID", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"])
            match_rows.append({
                "submission_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
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

        issue_rows: list[dict[str, Any]] = []
        for source_row in payload.issues:
            row = cast(dict[str, Any], clean_json(source_row))
            issue_rows.append({
                "submission_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
                "severity": _clip(row.get("Severity"), 30),
                "record_type": _clip(row.get("RecordType"), 50),
                "creature_id": _clip(row.get("CreatureID"), 120),
                "ua": _clip(row.get("UA"), 32),
                "issue": _clip(row.get("Issue")),
                "source_path": _clip(row.get("Path")),
                "raw_record": row,
            })

        discovery_queued = insert_conflict_safe(
            session,
            SubmittedDiscovery,
            discovery_rows,
            conflict_columns=["record_hash"],
        ) if discovery_rows else 0

        match_queued = insert_conflict_safe(
            session,
            SubmittedPetMatch,
            match_rows,
            conflict_columns=["record_hash"],
        ) if match_rows else 0

        if issue_rows:
            insert_plain(session, SubmissionIssue, issue_rows)

        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception(
            "Submission storage failed batch_id=%s contributor=%r save=%r discoveries=%s matches=%s issues=%s",
            batch_id,
            contributor,
            save_name,
            len(payload.discoveries),
            len(payload.matches),
            len(payload.issues),
        )
        raise HTTPException(
            status_code=500,
            detail=f"Submission could not be stored. Error reference: {batch_id}.",
        ) from exc

    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "submission_id": batch_id,
        "contributor": contributor,
        "save_name": save_name,
        "public_attribution": payload.publicAttribution,
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
