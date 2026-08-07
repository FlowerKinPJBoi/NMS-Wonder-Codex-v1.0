from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import AuditEvent, DaedalusCorpusEntry, DaedalusTrainingSubmission
from ..services.daedalus import (
    inspect_learning_package,
    read_learning_package,
    signed_learning_url,
    store_learning_package,
    verify_learning_package,
)
from ..services.daedalus_corpus import (
    corpus_counts,
    publish_lesson,
    retrieve_lessons,
    set_entry_active,
)
from ..services.security import OperatorSession, require_operator_key

router = APIRouter(prefix="/admin/apps/daedalus", tags=["daedalus-builder"])
STATUSES = {"pending_review", "needs_correction", "approved", "released", "rejected"}


class QueueAction(BaseModel):
    action: Literal["needs_correction", "approve", "release", "reject"]
    note: str = Field(default="", max_length=4000)


class CorpusDecision(BaseModel):
    action: Literal["index", "disable", "enable"]
    note: str = Field(min_length=1, max_length=4000)


class CorpusQuery(BaseModel):
    query: str = Field(default="", max_length=8000)
    domain: Literal["NO_MANS_SKY_CORVETTE_BUILDING", "NO_MANS_SKY_BASE_BUILDING"]
    category: str = Field(default="", max_length=120)
    style_tags: list[str] = Field(default_factory=list, max_length=40)
    object_ids: list[str] = Field(default_factory=list, max_length=250)
    part_count: int | None = Field(default=None, ge=1, le=3000)
    limit: int = Field(default=8, ge=1, le=20)


def _require(operator: OperatorSession, scope: str) -> None:
    if scope not in operator.scopes:
        raise HTTPException(status_code=403, detail="Your named operator does not have this Daedalus permission.")


def _corpus_public(entry: DaedalusCorpusEntry | None) -> dict:
    if entry is None:
        return {"status": "not_indexed", "active": False, "version": None}
    return {
        "status": entry.status,
        "active": entry.status == "active",
        "version": entry.published_version,
        "last_changed_version": entry.last_changed_version,
        "disabled_at": entry.disabled_at,
        "disabled_reason": entry.disabled_reason,
    }


def _public(row: DaedalusTrainingSubmission, corpus_entry: DaedalusCorpusEntry | None = None) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
        "released_at": row.released_at,
        "status": row.status,
        "contributor": row.contributor,
        "contributor_note": row.contributor_note,
        "reviewer": row.reviewer,
        "reviewer_note": row.reviewer_note,
        "original_filename": row.original_filename,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "schema_name": row.schema_name,
        "record_id": row.record_id,
        "domain": row.domain,
        "build_name": row.build_name,
        "ground_truth_format": row.ground_truth_format,
        "object_count": row.object_count,
        "distinct_object_ids": row.distinct_object_ids,
        "ground_truth_status": row.ground_truth_status,
        "attempt_status": row.attempt_status,
        "trust_collection": row.trust_collection,
        "server_validation": row.server_validation,
        "design_intent": row.design_intent,
        "corpus": _corpus_public(corpus_entry),
        "production_training_eligible": row.status == "released" and corpus_entry is not None and corpus_entry.status == "active",
    }


@router.get("")
def workspace(operator: OperatorSession = Depends(require_operator_key), session: Session = Depends(get_session)):
    _require(operator, "daedalus:submit")
    counts = {status: 0 for status in STATUSES}
    for status, count in session.execute(
        select(DaedalusTrainingSubmission.status, func.count(DaedalusTrainingSubmission.id)).group_by(
            DaedalusTrainingSubmission.status
        )
    ):
        counts[str(status)] = int(count)
    settings = get_settings()
    return {
        "operator": operator.actor,
        "permissions": {
            "submit": "daedalus:submit" in operator.scopes,
            "review": "daedalus:review" in operator.scopes,
            "release": "daedalus:release" in operator.scopes,
        },
        "counts": counts,
        "corpus": corpus_counts(session),
        "max_upload_bytes": settings.max_daedalus_package_bytes,
        "download_expires_seconds": settings.daedalus_download_seconds,
        "storage_ready": settings.spaces_private_ready,
        "production_rule": "Only released, active corpus lessons may influence Daedalus retrieval.",
    }


@router.get("/submissions")
def list_submissions(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    if status and status not in STATUSES:
        raise HTTPException(status_code=400, detail="Unknown Daedalus queue status.")
    statement = select(DaedalusTrainingSubmission).order_by(DaedalusTrainingSubmission.created_at.desc()).limit(limit)
    if status:
        statement = statement.where(DaedalusTrainingSubmission.status == status)
    rows = session.scalars(statement).all()
    entries = {}
    if rows:
        entries = {
            entry.submission_id: entry
            for entry in session.scalars(
                select(DaedalusCorpusEntry).where(DaedalusCorpusEntry.submission_id.in_([row.id for row in rows]))
            ).all()
        }
    return {"items": [_public(row, entries.get(row.id)) for row in rows]}


@router.post("/submissions")
async def submit_package(
    note: str = Form(default="", max_length=4000),
    archive: UploadFile = File(...),
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    settings = get_settings()
    raw = await archive.read(settings.max_daedalus_package_bytes + 1)
    package = inspect_learning_package(
        raw,
        archive.filename or "daedalus-learning-package.zip",
        maximum_bytes=settings.max_daedalus_package_bytes,
    )
    duplicate = session.scalar(select(DaedalusTrainingSubmission).where(DaedalusTrainingSubmission.sha256 == package.sha256))
    if duplicate:
        raise HTTPException(status_code=409, detail=f"This exact learning package is already {duplicate.status} as {duplicate.id}.")

    submission_id = str(uuid.uuid4())
    object_key = f"admin-apps/daedalus-training/{submission_id}/source.zip"
    store_learning_package(object_key, package, operator.actor)
    summary = package.summary
    row = DaedalusTrainingSubmission(
        id=submission_id,
        status="pending_review",
        contributor=operator.actor,
        contributor_note=" ".join(note.strip().split()),
        original_filename=package.filename,
        object_key=object_key,
        size_bytes=len(package.body),
        sha256=package.sha256,
        server_validation=package.validation,
        **summary,
    )
    session.add(row)
    session.add(AuditEvent(
        event_type="daedalus_training_submitted",
        actor=operator.actor,
        batch_id=submission_id,
        detail={"sha256": package.sha256, "recordId": row.record_id, "status": row.status},
    ))
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="This learning package or record was already submitted.") from exc
    return {"ok": True, "submission": _public(row)}


@router.patch("/submissions/{submission_id}")
def review_submission(
    submission_id: str,
    action: QueueAction,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:review")
    row = session.get(DaedalusTrainingSubmission, submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Daedalus submission not found.")
    if row.status == "released":
        raise HTTPException(status_code=409, detail="Released training records are immutable.")

    transitions = {
        "needs_correction": ({"pending_review", "approved"}, "needs_correction"),
        "approve": ({"pending_review", "needs_correction"}, "approved"),
        "release": ({"approved"}, "released"),
        "reject": ({"pending_review", "needs_correction", "approved"}, "rejected"),
    }
    allowed_from, target = transitions[action.action]
    if row.status not in allowed_from:
        raise HTTPException(status_code=409, detail=f"A {row.status} record cannot transition to {target}.")
    cleaned_note = " ".join(action.note.strip().split())
    if target in {"needs_correction", "rejected"} and not cleaned_note:
        raise HTTPException(status_code=400, detail="A reviewer note is required for this action.")
    if target == "released":
        _require(operator, "daedalus:release")
        if row.ground_truth_status != "verified":
            raise HTTPException(status_code=400, detail="Only human-verified ground truth may be released to production learning.")
        if not cleaned_note:
            raise HTTPException(status_code=400, detail="Record an explicit release decision before production learning.")
        verify_learning_package(row.object_key, expected_sha256=row.sha256, expected_size=row.size_bytes)
        package = read_learning_package(
            row.object_key,
            expected_sha256=row.sha256,
            expected_size=row.size_bytes,
            filename=row.original_filename,
            maximum_bytes=get_settings().max_daedalus_package_bytes,
        )

    previous_status = row.status
    now = datetime.now(timezone.utc)
    row.status = target
    row.reviewer = operator.actor
    row.reviewed_at = now
    if cleaned_note:
        row.reviewer_note = cleaned_note
    if target == "released":
        row.released_at = now
        corpus_entry = publish_lesson(
            session,
            row,
            package.record,
            actor=operator.actor,
            release_note=cleaned_note,
        )
    else:
        corpus_entry = None
    session.add(AuditEvent(
        event_type=f"daedalus_training_{target}",
        actor=operator.actor,
        batch_id=row.id,
        detail={
            "from": previous_status,
            "to": target,
            **({"corpusVersion": corpus_entry.published_version} if corpus_entry is not None else {}),
        },
    ))
    session.commit()
    return {"ok": True, "submission": _public(row, corpus_entry)}


@router.post("/corpus/retrieve")
def retrieve_corpus(
    request: CorpusQuery,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    invalid_ids = [value for value in request.object_ids if not value.startswith("^")]
    if invalid_ids:
        raise HTTPException(status_code=400, detail="Corpus Object ID filters must begin with ^.")
    return retrieve_lessons(
        session,
        query=" ".join(request.query.split()),
        domain=request.domain,
        category=request.category,
        style_tags=request.style_tags,
        object_ids=request.object_ids,
        part_count=request.part_count,
        limit=request.limit,
    )


@router.patch("/corpus/{submission_id}")
def change_corpus_entry(
    submission_id: str,
    decision: CorpusDecision,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:release")
    entry = session.scalar(select(DaedalusCorpusEntry).where(DaedalusCorpusEntry.submission_id == submission_id))
    if decision.action == "index":
        if entry is not None:
            raise HTTPException(status_code=409, detail="This released submission is already indexed.")
        row = session.get(DaedalusTrainingSubmission, submission_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Daedalus submission not found.")
        if row.status != "released":
            raise HTTPException(status_code=409, detail="Only released submissions may be indexed.")
        verify_learning_package(row.object_key, expected_sha256=row.sha256, expected_size=row.size_bytes)
        package = read_learning_package(
            row.object_key,
            expected_sha256=row.sha256,
            expected_size=row.size_bytes,
            filename=row.original_filename,
            maximum_bytes=get_settings().max_daedalus_package_bytes,
        )
        entry = publish_lesson(
            session,
            row,
            package.record,
            actor=operator.actor,
            release_note=decision.note,
        )
        version = entry.published_version
        session.add(AuditEvent(
            event_type="daedalus_corpus_indexed",
            actor=operator.actor,
            batch_id=submission_id,
            detail={"corpusVersion": version, "reason": " ".join(decision.note.split())},
        ))
        session.commit()
        return {"ok": True, "corpus": _corpus_public(entry), "corpus_version": version}
    if entry is None:
        raise HTTPException(status_code=404, detail="Index this released submission before changing its corpus state.")
    version = set_entry_active(
        session,
        entry,
        active=decision.action == "enable",
        reason=decision.note,
    )
    session.add(AuditEvent(
        event_type=f"daedalus_corpus_{decision.action}d",
        actor=operator.actor,
        batch_id=submission_id,
        detail={"corpusVersion": version, "reason": " ".join(decision.note.split())},
    ))
    session.commit()
    return {"ok": True, "corpus": _corpus_public(entry), "corpus_version": version}


@router.post("/submissions/{submission_id}/download")
def download_submission(
    submission_id: str,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    row = session.get(DaedalusTrainingSubmission, submission_id)
    if not row:
        raise HTTPException(status_code=404, detail="Daedalus submission not found.")
    return {
        "download_url": signed_learning_url(row.object_key, row.original_filename),
        "filename": row.original_filename,
        "sha256": row.sha256,
        "expires_seconds": get_settings().daedalus_download_seconds,
    }
