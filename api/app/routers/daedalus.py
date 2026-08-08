from __future__ import annotations

from functools import partial
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..config import get_settings
from ..database import get_session
from ..models import (
    AuditEvent,
    DaedalusBuildPass,
    DaedalusBuildSession,
    DaedalusCorpusEntry,
    DaedalusTrainingSubmission,
)
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
from ..services.daedalus_build_storage import read_build_artifact, signed_build_url, store_build_artifact
from ..services.daedalus_builder import generate_build, parse_build, safe_build_filename
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


ALLOWED_REFERENCE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def _valid_reference_signature(content_type: str, body: bytes) -> bool:
    if content_type == "image/png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return body.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP"
    return False


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


def _build_session_public(row: DaedalusBuildSession) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "status": row.status,
        "source_filename": row.source_filename,
        "source_format": row.source_format,
        "source_sha256": row.source_sha256,
        "source_size_bytes": row.source_size_bytes,
        "latest_version": row.latest_version,
        "source_validation": row.source_validation,
    }


def _build_pass_public(row: DaedalusBuildPass) -> dict:
    return {
        "id": row.id,
        "version": row.version,
        "created_at": row.created_at,
        "instruction": row.instruction,
        "filename": row.output_filename,
        "sha256": row.output_sha256,
        "size_bytes": row.output_size_bytes,
        "object_count": row.object_count,
        "distinct_object_ids": row.distinct_object_ids,
        "operation_count": row.operation_count,
        "corpus_version": row.corpus_version,
        "model": row.model_name,
        "plan": row.plan,
        "validation": row.validation,
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
        "generation": {
            "ready": settings.daedalus_generation_ready,
            "model": settings.daedalus_model,
            "maximum_operations_per_pass": settings.max_daedalus_operations,
            "maximum_references": settings.max_daedalus_references,
            "setup_required": None if settings.daedalus_generation_ready else "Add OPENAI_API_KEY to the API service's encrypted environment settings.",
        },
        "production_rule": "Only released, active corpus lessons may influence Daedalus retrieval.",
    }


def _build_category(instruction: str) -> str:
    text = instruction.casefold()
    for category, words in (
        ("sign", ("sign", "letter", "marquee")),
        ("building", ("base", "building", "interior", "decorate", "room", "stairs")),
        ("sailing ship", ("sailing", "galleon", "sail", "mast")),
        ("saucer", ("saucer", "ufo", "disc")),
        ("sci-fi", ("corvette", "ship", "starship", "spacecraft")),
    ):
        if any(word in text for word in words):
            return category
    return "other"


def _retrieve_for_build(session: Session, parsed, instruction: str) -> dict:
    object_ids = list(dict.fromkeys(
        str(item.get("ObjectID") or "") for item in parsed.objects if str(item.get("ObjectID") or "").startswith("^")
    ))[:250]
    domain = "NO_MANS_SKY_CORVETTE_BUILDING" if parsed.format == "nmsship" else "NO_MANS_SKY_BASE_BUILDING"
    return retrieve_lessons(
        session,
        query=instruction,
        domain=domain,
        category=_build_category(instruction),
        object_ids=object_ids,
        part_count=max(1, len(parsed.objects)),
        limit=6,
    )


async def _reference_bodies(files: list[UploadFile], settings) -> list[tuple[str, bytes]]:
    if len(files) > settings.max_daedalus_references:
        raise HTTPException(status_code=400, detail=f"Add no more than {settings.max_daedalus_references} reference images per pass.")
    output: list[tuple[str, bytes]] = []
    for upload in files:
        content_type = (upload.content_type or "").casefold()
        if content_type not in ALLOWED_REFERENCE_TYPES:
            raise HTTPException(status_code=400, detail="Daedalus reference images must be PNG, JPEG, or WebP.")
        body = await upload.read(settings.max_daedalus_reference_bytes + 1)
        if not body or len(body) > settings.max_daedalus_reference_bytes:
            raise HTTPException(status_code=413, detail="A Daedalus reference image exceeds the configured limit.")
        if not _valid_reference_signature(content_type, body):
            raise HTTPException(status_code=400, detail="A Daedalus reference image does not match its declared PNG, JPEG, or WebP type.")
        output.append((content_type, body))
    return output


def _generated_response(build_session: DaedalusBuildSession, build_pass: DaedalusBuildPass) -> dict:
    file_path = f"/api/admin/apps/daedalus/build-sessions/{build_session.id}/passes/{build_pass.version}/file"
    return {
        "ok": True,
        "session": _build_session_public(build_session),
        "pass": _build_pass_public(build_pass),
        "file_path": file_path,
    }


@router.post("/build-sessions")
async def create_build_session(
    instruction: str = Form(..., min_length=1, max_length=8000),
    source: UploadFile = File(...),
    references: list[UploadFile] | None = File(default=None),
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    settings = get_settings()
    if not settings.spaces_private_ready:
        raise HTTPException(status_code=503, detail="Private Daedalus build storage is not configured yet.")
    if not settings.openai_api_key.strip():
        raise HTTPException(status_code=503, detail="Daedalus generation needs OPENAI_API_KEY in the API service's encrypted environment settings.")
    raw = await source.read(settings.max_daedalus_build_bytes + 1)
    if len(raw) > settings.max_daedalus_build_bytes:
        raise HTTPException(status_code=413, detail="The Daedalus source build exceeds the configured limit.")
    parsed = parse_build(raw, source.filename or "daedalus-build.json")
    reference_bodies = await _reference_bodies(references or [], settings)
    retrieval = _retrieve_for_build(session, parsed, instruction)
    generated = await run_in_threadpool(partial(
        generate_build,
        parsed,
        instruction,
        retrieval,
        [],
        reference_bodies,
        settings,
        version=1,
    ))

    session_id = str(uuid.uuid4())
    source_key = f"admin-apps/daedalus-builds/{session_id}/source/{parsed.filename}"
    output_key = f"admin-apps/daedalus-builds/{session_id}/passes/1/{generated.filename}"
    source_digest, source_size = await run_in_threadpool(store_build_artifact, source_key, raw, parsed.filename, operator.actor)
    output_digest, output_size = await run_in_threadpool(store_build_artifact, output_key, generated.body, generated.filename, operator.actor)
    build_session = DaedalusBuildSession(
        id=session_id,
        actor=operator.actor,
        status="active",
        source_filename=parsed.filename,
        source_format=parsed.format,
        source_object_key=source_key,
        source_sha256=source_digest,
        source_size_bytes=source_size,
        source_validation=parsed.validation,
        latest_version=1,
    )
    build_pass = DaedalusBuildPass(
        id=str(uuid.uuid4()),
        session_id=session_id,
        version=1,
        instruction=" ".join(instruction.split()),
        output_filename=generated.filename,
        output_object_key=output_key,
        output_sha256=output_digest,
        output_size_bytes=output_size,
        object_count=generated.object_count,
        distinct_object_ids=generated.distinct_object_ids,
        operation_count=generated.operation_count,
        corpus_version=int(retrieval.get("corpus_version") or 0),
        model_name=settings.daedalus_model,
        provider_response_id=generated.provider_response_id,
        plan=generated.plan,
        validation=generated.validation,
    )
    session.add(build_session)
    session.add(build_pass)
    session.add(AuditEvent(
        event_type="daedalus_build_pass_generated",
        actor=operator.actor,
        batch_id=session_id,
        detail={"version": 1, "operations": generated.operation_count, "sha256": output_digest},
    ))
    session.commit()
    return _generated_response(build_session, build_pass)


def _owned_build_session(session_id: str, operator: OperatorSession, session: Session) -> DaedalusBuildSession:
    row = session.get(DaedalusBuildSession, session_id)
    if row is None or row.actor != operator.actor:
        raise HTTPException(status_code=404, detail="Daedalus build session not found for this trainer.")
    return row


@router.post("/build-sessions/{session_id}/passes")
async def create_build_pass(
    session_id: str,
    instruction: str = Form(..., min_length=1, max_length=8000),
    references: list[UploadFile] | None = File(default=None),
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    settings = get_settings()
    if not settings.daedalus_generation_ready:
        raise HTTPException(status_code=503, detail="Daedalus generation needs private storage and OPENAI_API_KEY.")
    build_session = _owned_build_session(session_id, operator, session)
    starting_version = build_session.latest_version
    previous = session.scalar(
        select(DaedalusBuildPass).where(
            DaedalusBuildPass.session_id == session_id,
            DaedalusBuildPass.version == build_session.latest_version,
        )
    )
    if previous is None:
        raise HTTPException(status_code=409, detail="The prior Daedalus build pass is missing.")
    raw = await run_in_threadpool(partial(
        read_build_artifact,
        previous.output_object_key,
        maximum_bytes=settings.max_daedalus_build_bytes,
        expected_sha256=previous.output_sha256,
        expected_size=previous.output_size_bytes,
    ))
    parsed = parse_build(raw, previous.output_filename)
    parsed.filename = build_session.source_filename
    reference_bodies = await _reference_bodies(references or [], settings)
    retrieval = _retrieve_for_build(session, parsed, instruction)
    prior_rows = session.scalars(
        select(DaedalusBuildPass).where(DaedalusBuildPass.session_id == session_id).order_by(DaedalusBuildPass.version)
    ).all()
    history = [{
        "version": row.version,
        "instruction": row.instruction,
        "summary": (row.plan or {}).get("summary"),
        "warnings": (row.plan or {}).get("warnings") or [],
    } for row in prior_rows[-6:]]
    version = starting_version + 1
    generated = await run_in_threadpool(partial(
        generate_build,
        parsed,
        instruction,
        retrieval,
        history,
        reference_bodies,
        settings,
        version=version,
    ))
    pass_id = str(uuid.uuid4())
    output_key = f"admin-apps/daedalus-builds/{session_id}/passes/{version}-{pass_id}/{generated.filename}"
    output_digest, output_size = await run_in_threadpool(store_build_artifact, output_key, generated.body, generated.filename, operator.actor)
    locked_session = session.scalar(
        select(DaedalusBuildSession)
        .where(DaedalusBuildSession.id == session_id, DaedalusBuildSession.actor == operator.actor)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_session is None or locked_session.latest_version != starting_version:
        raise HTTPException(status_code=409, detail="A newer Daedalus pass finished first. Retry this revision against the latest pass.")
    build_session = locked_session
    build_pass = DaedalusBuildPass(
        id=pass_id,
        session_id=session_id,
        version=version,
        instruction=" ".join(instruction.split()),
        output_filename=generated.filename,
        output_object_key=output_key,
        output_sha256=output_digest,
        output_size_bytes=output_size,
        object_count=generated.object_count,
        distinct_object_ids=generated.distinct_object_ids,
        operation_count=generated.operation_count,
        corpus_version=int(retrieval.get("corpus_version") or 0),
        model_name=settings.daedalus_model,
        provider_response_id=generated.provider_response_id,
        plan=generated.plan,
        validation=generated.validation,
    )
    build_session.latest_version = version
    session.add(build_pass)
    session.add(AuditEvent(
        event_type="daedalus_build_pass_generated",
        actor=operator.actor,
        batch_id=session_id,
        detail={"version": version, "operations": generated.operation_count, "sha256": output_digest},
    ))
    session.commit()
    return _generated_response(build_session, build_pass)


@router.get("/build-sessions/{session_id}")
def get_build_session(
    session_id: str,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    build_session = _owned_build_session(session_id, operator, session)
    passes = session.scalars(
        select(DaedalusBuildPass).where(DaedalusBuildPass.session_id == session_id).order_by(DaedalusBuildPass.version)
    ).all()
    return {"session": _build_session_public(build_session), "passes": [_build_pass_public(row) for row in passes]}


def _owned_build_pass(session_id: str, version: int, operator: OperatorSession, session: Session) -> tuple[DaedalusBuildSession, DaedalusBuildPass]:
    build_session = _owned_build_session(session_id, operator, session)
    build_pass = session.scalar(select(DaedalusBuildPass).where(
        DaedalusBuildPass.session_id == session_id,
        DaedalusBuildPass.version == version,
    ))
    if build_pass is None:
        raise HTTPException(status_code=404, detail="Daedalus build pass not found.")
    return build_session, build_pass


@router.get("/build-sessions/{session_id}/passes/{version}/file")
async def read_build_pass_file(
    session_id: str,
    version: int,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    _, build_pass = _owned_build_pass(session_id, version, operator, session)
    body = await run_in_threadpool(partial(
        read_build_artifact,
        build_pass.output_object_key,
        maximum_bytes=get_settings().max_daedalus_build_bytes,
        expected_sha256=build_pass.output_sha256,
        expected_size=build_pass.output_size_bytes,
    ))
    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_build_filename(build_pass.output_filename)}"'},
    )


@router.post("/build-sessions/{session_id}/passes/{version}/download")
def download_build_pass(
    session_id: str,
    version: int,
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    _require(operator, "daedalus:submit")
    _, build_pass = _owned_build_pass(session_id, version, operator, session)
    return {
        "download_url": signed_build_url(build_pass.output_object_key, build_pass.output_filename),
        "filename": build_pass.output_filename,
        "sha256": build_pass.output_sha256,
        "expires_seconds": get_settings().daedalus_download_seconds,
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
