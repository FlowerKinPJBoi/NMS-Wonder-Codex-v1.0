from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import check_database, get_session
from ..models import Discovery, ImageContribution
from ..services.catalog import wc_id
from ..services.rate_limit import enforce
from ..services.storage import get_object, prepare_upload, put_pending

router = APIRouter(prefix="/images", tags=["images"])

ALLOWED_ROLES = {
    "primary_catalog",
    "full_specimen",
    "side_view",
    "front_view",
    "scale_reference",
    "environment",
    "projector_confirmation",
    "portal_location_evidence",
}


@router.post("")
async def submit_image(
    request: Request,
    discovery_id: int = Form(...),
    contributor: str = Form(..., min_length=2, max_length=120),
    image_role: str = Form(...),
    caption: str = Form(default="", max_length=2000),
    permission_confirmed: bool = Form(...),
    website: str = Form(default=""),
    image: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    if website:
        return {"ok": True, "queued": False}
    if not permission_confirmed:
        raise HTTPException(status_code=400, detail="Image display permission must be confirmed.")
    if image_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Unknown image role.")
    if not check_database():
        raise HTTPException(status_code=503, detail="Wonder Database is temporarily unavailable.")

    contributor = " ".join(contributor.strip().split())
    if contributor.lower() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")
    discovery = session.get(Discovery, discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")

    ip_hash = enforce(request)
    prepared = await prepare_upload(image)
    digest = hashlib.sha256(prepared.body).hexdigest()
    duplicate = session.scalar(select(ImageContribution).where(
        ImageContribution.discovery_id == discovery.id,
        ImageContribution.sha256 == digest,
        ImageContribution.status.in_(["pending", "approved"]),
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="This image has already been submitted for this Wonder.")

    image_id = str(uuid.uuid4())
    object_key = f"pending/{discovery.id}/{image_id}.webp"
    put_pending(object_key, prepared)

    row = ImageContribution(
        id=image_id,
        discovery_id=discovery.id,
        contributor=contributor,
        image_role=image_role,
        caption=caption.strip(),
        permission_confirmed=True,
        status="pending",
        object_key=object_key,
        original_filename=prepared.original_filename,
        content_type=prepared.content_type,
        width=prepared.width,
        height=prepared.height,
        size_bytes=len(prepared.body),
        sha256=digest,
        submitter_ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent", "")[:1000],
    )
    session.add(row)
    if discovery.image_status == "needed":
        discovery.image_status = "pending"
    session.commit()
    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "image_id": image_id,
        "wc_id": wc_id(discovery),
        "width": prepared.width,
        "height": prepared.height,
    }


@router.get("/{image_id}/content", include_in_schema=False)
def approved_image_content(
    image_id: str,
    request: Request,
    session: Session = Depends(get_session),
):
    row = session.get(ImageContribution, image_id)
    if not row or row.status != "approved":
        raise HTTPException(status_code=404, detail="Approved image not found.")
    if not row.object_key:
        raise HTTPException(status_code=404, detail="Approved image file is unavailable.")

    stored = get_object(row.object_key)
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'inline; filename="wonder-{row.discovery_id}-{row.id}.webp"',
        "X-Content-Type-Options": "nosniff",
    }
    if stored.etag:
        headers["ETag"] = stored.etag
        if request.headers.get("if-none-match") == stored.etag:
            stored.body.close()
            return Response(status_code=304, headers=headers)
    if stored.content_length is not None:
        headers["Content-Length"] = str(stored.content_length)

    def chunks():
        try:
            for chunk in stored.body.iter_chunks(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            stored.body.close()

    return StreamingResponse(chunks(), media_type=stored.content_type, headers=headers)


@router.get("/{image_id}")
def image_status(image_id: str, session: Session = Depends(get_session)):
    row = session.get(ImageContribution, image_id)
    if not row:
        raise HTTPException(status_code=404, detail="Image submission not found.")
    discovery = session.get(Discovery, row.discovery_id)
    return {
        "id": row.id,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "wc_id": wc_id(discovery) if discovery else None,
        "reviewer_note": row.reviewer_note,
        "public_url": f"/api/images/{row.id}/content" if row.status == "approved" else "",
    }
