from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import check_database, get_session
from ..models import CaptureSubmission
from ..services.hashing import canonical_hash
from ..services.rate_limit import client_ip
from ..services.sanitization import clean_json, safe_text
from ..services.security import OperatorSession, require_operator_key
from ..services.storage import prepare_upload, put_pending


router = APIRouter(prefix="/captures", tags=["captures"])
ALLOWED_ROLES = {"full_specimen", "side_view", "front_view", "environment", "projector_confirmation"}


def _text(value: Any, limit: int) -> str:
    return safe_text(value)[:limit]


def normalize_capture_discovery(source: dict[str, Any]) -> dict[str, Any]:
    """Reduce a local capture to the same privacy-safe fields as a WCCP discovery."""
    cleaned = clean_json(source)
    if not isinstance(cleaned, dict):
        raise ValueError("Discovery data must be a JSON object.")

    vp_source = cleaned.get("VP") if isinstance(cleaned.get("VP"), list) else []
    vp = [
        _text(cleaned.get(f"VP{index}") or (vp_source[index] if index < len(vp_source) else ""), 32)
        for index in range(5)
    ]
    discovery_type = _text(cleaned.get("DT") or cleaned.get("DiscoveryType"), 40)
    ua = _text(cleaned.get("UA") or cleaned.get("UniversalAddress"), 32)
    if not discovery_type or not ua:
        raise ValueError("A discovery type and Universal Address are required.")

    descriptors = cleaned.get("Descriptors")
    if not isinstance(descriptors, list):
        descriptors = []
    normalized = {
        "DT": discovery_type,
        "UA": ua,
        **{f"VP{index}": vp[index] for index in range(5)},
        "MessageID": _text(cleaned.get("MessageID"), 20000),
        "CreatureID": _text(cleaned.get("CreatureID"), 120),
        "CreatureType": _text(cleaned.get("CreatureType"), 120),
        "Descriptors": [_text(item, 160) for item in descriptors[:100] if _text(item, 160)],
        "CustomName": _text(cleaned.get("CustomName"), 200),
        "SensorEventID": _text(cleaned.get("SensorEventID"), 120),
    }
    return normalized


@router.post("")
async def submit_capture(
    request: Request,
    save_name: str = Form(default="", max_length=200),
    platform: str = Form(default="", max_length=40),
    client_version: str = Form(default="", max_length=80),
    discovery_json: str = Form(...),
    image_role: str = Form(default="full_specimen"),
    caption: str = Form(default="", max_length=2000),
    permission_confirmed: bool = Form(...),
    public_attribution: bool = Form(default=True),
    image: UploadFile = File(...),
    operator: OperatorSession = Depends(require_operator_key),
    session: Session = Depends(get_session),
):
    if "capture:submit" not in operator.scopes:
        raise HTTPException(status_code=403, detail="Capture submission access is required.")
    if not permission_confirmed:
        raise HTTPException(status_code=400, detail="Image display permission must be confirmed.")
    if image_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Unknown image role.")
    if not check_database():
        raise HTTPException(status_code=503, detail="Wonder Database is temporarily unavailable.")
    if len(discovery_json.encode("utf-8")) > 200_000:
        raise HTTPException(status_code=413, detail="Normalized discovery data is too large.")

    try:
        source = json.loads(discovery_json)
        normalized = normalize_capture_discovery(source)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prepared = await prepare_upload(image)
    image_digest = hashlib.sha256(prepared.body).hexdigest()
    record_hash = canonical_hash(normalized, ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"])
    duplicate = session.scalar(
        select(CaptureSubmission).where(
            CaptureSubmission.record_hash == record_hash,
            CaptureSubmission.sha256 == image_digest,
            CaptureSubmission.status.in_(["pending", "approved"]),
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"This confirmed pair is already {duplicate.status} as {duplicate.id}.",
        )

    capture_id = str(uuid.uuid4())
    object_key = f"capture-pending/{capture_id}.webp"
    put_pending(object_key, prepared)
    settings = get_settings()
    ip_digest = hashlib.sha256(
        f"{settings.ip_hash_salt}:{client_ip(request)}".encode("utf-8")
    ).hexdigest()
    row = CaptureSubmission(
        id=capture_id,
        contributor=operator.actor,
        save_name=" ".join(save_name.strip().split())[:200],
        platform=" ".join(platform.strip().split())[:40],
        client_version=client_version.strip()[:80],
        public_attribution=public_attribution,
        discovery_type=normalized["DT"],
        ua=normalized["UA"],
        vp0=normalized["VP0"],
        vp1=normalized["VP1"],
        vp2=normalized["VP2"],
        vp3=normalized["VP3"],
        vp4=normalized["VP4"],
        message_id=normalized["MessageID"],
        creature_id=normalized["CreatureID"],
        creature_type=normalized["CreatureType"],
        record_hash=record_hash,
        discovery_record=normalized,
        image_role=image_role,
        caption=caption.strip(),
        permission_confirmed=True,
        object_key=object_key,
        original_filename=prepared.original_filename,
        content_type=prepared.content_type,
        width=prepared.width,
        height=prepared.height,
        size_bytes=len(prepared.body),
        sha256=image_digest,
        submitter_ip_hash=ip_digest,
        user_agent=request.headers.get("user-agent", "")[:1000],
    )
    session.add(row)
    session.commit()
    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "capture_id": capture_id,
        "contributor": operator.actor,
        "discovery_type": normalized["DT"],
    }

