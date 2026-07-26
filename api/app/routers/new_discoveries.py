from __future__ import annotations

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import check_database, get_session
from ..models import NewDiscoverySubmission
from ..services.rate_limit import enforce
from ..services.storage import prepare_upload, put_pending


router = APIRouter(prefix="/new-discoveries", tags=["new-discoveries"])
ALLOWED_TYPES = {"Animal", "Flora", "Mineral"}
ALLOWED_PLATFORMS = {"", "xbox", "playstation", "switch", "steam"}


@router.post("")
async def submit_new_discovery(
    request: Request,
    contributor: str = Form(..., min_length=2, max_length=120),
    discovery_type: str = Form(...),
    display_name: str = Form(default="", max_length=200),
    platform: str = Form(default="", max_length=40),
    galaxy_number: int | None = Form(default=None, ge=1, le=256),
    galaxy_name: str = Form(default="", max_length=120),
    portal_glyphs: str = Form(default="", max_length=12),
    notes: str = Form(default="", max_length=4000),
    permission_confirmed: bool = Form(...),
    public_attribution: bool = Form(default=True),
    website: str = Form(default=""),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if website:
        return {"ok": True, "queued": False}
    if not permission_confirmed:
        raise HTTPException(status_code=400, detail="Image display permission must be confirmed.")
    if discovery_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Choose Fauna, Flora, or Mineral.")
    platform = platform.strip().casefold()
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=400, detail="Unknown NMS platform.")
    glyphs = re.sub(r"[^0-9A-F]", "", portal_glyphs.upper())
    if glyphs and len(glyphs) != 12:
        raise HTTPException(status_code=400, detail="Portal glyph code must contain all 12 glyphs or be blank.")
    if not check_database():
        raise HTTPException(status_code=503, detail="Wonder Database is temporarily unavailable.")

    contributor = " ".join(contributor.strip().split())
    if contributor.casefold() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")
    prepared = await prepare_upload(image)
    digest = hashlib.sha256(prepared.body).hexdigest()
    duplicate = session.scalar(select(NewDiscoverySubmission).where(
        NewDiscoverySubmission.sha256 == digest,
        NewDiscoverySubmission.status.in_(["pending", "approved"]),
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="This screenshot is already in the new-discovery queue.")

    intake_id = str(uuid.uuid4())
    object_key = f"pending/new-discoveries/{intake_id}.webp"
    put_pending(object_key, prepared)
    row = NewDiscoverySubmission(
        id=intake_id,
        contributor=contributor,
        public_attribution=public_attribution,
        discovery_type=discovery_type,
        display_name=" ".join(display_name.strip().split()),
        platform=platform,
        galaxy_number=galaxy_number,
        galaxy_name=" ".join(galaxy_name.strip().split()),
        portal_glyphs=glyphs,
        notes=notes.strip(),
        permission_confirmed=True,
        object_key=object_key,
        original_filename=prepared.original_filename,
        content_type=prepared.content_type,
        width=prepared.width,
        height=prepared.height,
        size_bytes=len(prepared.body),
        sha256=digest,
        submitter_ip_hash=enforce(request),
        user_agent=request.headers.get("user-agent", "")[:1000],
    )
    session.add(row)
    session.commit()
    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "intake_id": intake_id,
        "reference": f"NEW-{intake_id.split('-')[0].upper()}",
        "width": prepared.width,
        "height": prepared.height,
        "public_attribution": public_attribution,
    }


@router.get("/{intake_id}")
def new_discovery_status(intake_id: str, session: Session = Depends(get_session)):
    row = session.get(NewDiscoverySubmission, intake_id)
    if not row:
        raise HTTPException(status_code=404, detail="New discovery submission not found.")
    return {
        "id": row.id,
        "reference": f"NEW-{row.id.split('-')[0].upper()}",
        "status": row.status,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "published_discovery_id": row.published_discovery_id,
        "reviewer_note": row.reviewer_note,
    }
