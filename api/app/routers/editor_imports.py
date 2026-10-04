from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import check_database, get_session
from ..models import AssetSpecimen, AuditEvent, EditorImportReceipt, SubmissionBatch, SubmittedDiscovery, SubmittedPetMatch, UserProfile
from ..services.bulk import insert_conflict_safe
from ..services.capture_auth import enforce_auth_rate, rate_for_request
from ..services.editor_auth import require_editor_submitter
from ..services.editor_imports import (
    ASSET_TYPES, DISCOVERY_TYPES, MAX_RECORDS, MAX_REQUEST_BYTES, SCHEMA,
    EditorImportPayload, normalized_asset, normalized_discovery,
)
from ..services.hashing import canonical_hash, fingerprint
from ..services.rate_limit import client_ip

router = APIRouter(prefix="/editor", tags=["editor-imports"])


@router.get("/capabilities")
def capabilities():
    database_ready = check_database()
    return {"schema": SCHEMA, "max_records": MAX_RECORDS, "max_request_bytes": MAX_REQUEST_BYTES,
            "discovery_types": DISCOVERY_TYPES, "asset_types": ASSET_TYPES,
            "passport_path": "/api/auth/editor/start", "submission_path": "/api/editor/imports",
            "passport_ready": get_settings().accounts_ready, "database_ready": database_ready,
            "ready": database_ready and get_settings().accounts_ready, "access_tiers": ["tester", "admin"],
            "publication": "owner_review_required"}


def existing_receipt(session: Session, profile_id: str, key: str, request_hash: str) -> dict | None:
    receipt = session.scalar(select(EditorImportReceipt).where(
        EditorImportReceipt.profile_id == profile_id, EditorImportReceipt.idempotency_key == key))
    if receipt is None:
        return None
    if receipt.request_hash != request_hash:
        raise HTTPException(409, "This import request key was already used for a different selection. Create a new request key.")
    if not receipt.response:
        raise HTTPException(409, "This import request is still being processed. Retry the same request shortly.")
    return {**receipt.response, "replayed": True}


@router.post("/imports")
def submit(payload: EditorImportPayload, request: Request,
           idempotency_key: str = Header(alias="Idempotency-Key", min_length=36, max_length=36),
           profile: UserProfile = Depends(require_editor_submitter), session: Session = Depends(get_session)):
    try:
        key = str(uuid.UUID(idempotency_key))
    except ValueError as exc:
        raise HTTPException(400, "Idempotency-Key must be a UUID generated for this selection.") from exc
    request_hash = fingerprint(payload.model_dump(mode="json", by_alias=True))
    previous = existing_receipt(session, profile.id, key, request_hash)
    if previous is not None:
        return previous
    # These shared database throttles commit before the import transaction starts.
    rate_for_request(session, request, "editor-import", 60)
    enforce_auth_rate(session, f"editor-import-user:{profile.id}", 30)
    receipt_id = str(uuid.uuid4())
    insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else pg_insert
    claimed = session.scalar(insert(EditorImportReceipt).values(
        id=receipt_id, profile_id=profile.id, idempotency_key=key, request_hash=request_hash, response={},
    ).on_conflict_do_nothing(index_elements=["profile_id", "idempotency_key"]).returning(EditorImportReceipt.id))
    if claimed is None:
        previous = existing_receipt(session, profile.id, key, request_hash)
        if previous is not None:
            return previous
        raise HTTPException(409, "Import is being processed. Retry the same request shortly.")

    batch_id = str(uuid.uuid4())
    attribution = payload.public_attribution and profile.public_attribution
    source_name = "Selected editor save"
    batch = SubmissionBatch(
        id=batch_id, contributor=profile.contributor_name, save_name=source_name,
        platform=payload.platform, client_version=payload.client_version, status="pending",
        source_fingerprint=request_hash,
        summary={"source": "wonder_codex_editor", "discoveries": len(payload.discoveries), "assets": len(payload.assets)},
        submitter_ip_hash=hashlib.sha256(f"{get_settings().ip_hash_salt}:{client_ip(request)}".encode()).hexdigest(),
        user_agent=request.headers.get("user-agent", "")[:1000], public_attribution=attribution,
    )
    session.add(batch)
    session.flush()
    discoveries, matches, assets = [], [], []
    for source in payload.discoveries:
        row, record_hash = normalized_discovery(source)
        discoveries.append({
            "submission_batch_id": batch_id, "contributor": profile.contributor_name, "save_name": source_name,
            "discovery_type": row["DT"], "ua": row["UA"],
            **{f"vp{i}": row[f"VP{i}"] for i in range(5)}, "message_id": row["MessageID"],
            "owner": "", "platform": payload.platform, "source_path": "", "record_hash": record_hash,
            "review_status": "pending", "raw_record": row,
        })
        if source.CreatureID:
            # Client claims an exact local join; retain it for owner review, never verify it automatically.
            match = {**row, "SecondarySeed": "", "SecondaryCheck": "Unavailable",
                     "EvidenceStatus": "client_reports_exact_pet_join"}
            matches.append({
                "submission_batch_id": batch_id, "contributor": profile.contributor_name, "save_name": source_name,
                "creature_id": source.CreatureID, "creature_type": source.CreatureType, "ua": row["UA"],
                **{f"vp{i}": row[f"VP{i}"] for i in range(5)}, "message_id": row["MessageID"],
                "secondary_seed": "", "secondary_check": "Unavailable", "pet_path": "", "discovery_path": "",
                "record_hash": canonical_hash(match, ["CreatureID", "UA", *[f"VP{i}" for i in range(max(5, len(source.VP)))]]),
                "review_status": "pending", "raw_record": match,
            })
    for source in payload.assets:
        assets.append({**normalized_asset(source), "contributor": profile.contributor_name, "save_name": source_name,
                       "platform": payload.platform, "public_attribution": attribution,
                       "image_status": "needed", "reviewer_note": f"Editor import {batch_id}; current save evidence only."})

    # Existing rows, including published assets, are never overwritten by a contributor.
    queued = {
        "discoveries": insert_conflict_safe(session, SubmittedDiscovery, discoveries, conflict_columns=["record_hash"]) if discoveries else 0,
        "pet_matches": insert_conflict_safe(session, SubmittedPetMatch, matches, conflict_columns=["record_hash"]) if matches else 0,
        "assets": insert_conflict_safe(session, AssetSpecimen, assets, conflict_columns=["asset_key"]) if assets else 0,
    }
    duplicate = {"discoveries": len(discoveries) - queued["discoveries"],
                 "pet_matches": len(matches) - queued["pet_matches"], "assets": len(assets) - queued["assets"]}
    response = {"ok": True, "submission_id": batch_id, "status": "pending_review", "pending_review": True,
                "accepted": queued["discoveries"] + queued["assets"],
                "duplicates": duplicate["discoveries"] + duplicate["assets"], "rejected": 0,
                "queued_records": queued, "duplicates_skipped": duplicate,
                "contributor": profile.contributor_name, "public_attribution": attribution, "replayed": False}
    receipt = session.get(EditorImportReceipt, receipt_id)
    receipt.response = response
    session.add(AuditEvent(event_type="editor_import_submitted", actor=profile.contributor_name,
                           batch_id=batch_id, detail={"receipt_id": receipt_id, "queued_records": queued,
                                                       "duplicates_skipped": duplicate, "schema": SCHEMA}))
    session.commit()
    return response
