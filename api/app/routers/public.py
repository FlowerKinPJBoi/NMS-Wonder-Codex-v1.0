from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import Discovery, ImageContribution, LocationVerification, PetDiscoveryMatch, SubmissionBatch
from ..services.catalog import serialize_discovery

router = APIRouter(tags=["public"])


def image_delivery_url(image: ImageContribution | None) -> str:
    return f"/api/images/{image.id}/content" if image else ""



@router.get("/stats")
def public_stats(session: Session = Depends(get_session)):
    type_rows = session.execute(
        select(Discovery.discovery_type, func.count(Discovery.id))
        .group_by(Discovery.discovery_type)
    ).all()
    type_counts = {str(name): int(count) for name, count in type_rows}

    latest_approved_at = session.scalar(
        select(func.max(SubmissionBatch.reviewed_at)).where(SubmissionBatch.status == "approved")
    )

    return {
        "published_discoveries": session.scalar(select(func.count()).select_from(Discovery)) or 0,
        "published_pet_matches": session.scalar(select(func.count()).select_from(PetDiscoveryMatch)) or 0,
        "pending_submissions": session.scalar(
            select(func.count()).select_from(SubmissionBatch).where(SubmissionBatch.status == "pending")
        ) or 0,
        "pending_images": session.scalar(
            select(func.count()).select_from(ImageContribution).where(ImageContribution.status == "pending")
        ) or 0,
        "pending_verifications": session.scalar(
            select(func.count()).select_from(LocationVerification).where(LocationVerification.status == "pending")
        ) or 0,
        "verified_locations": session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.location_status == "verified")
        ) or 0,
        "images_needed": session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.image_status == "needed")
        ) or 0,
        "contributors": session.scalar(
            select(func.count(distinct(Discovery.contributor))).select_from(Discovery)
        ) or 0,
        "types": {
            "Animal": type_counts.get("Animal", 0),
            "Flora": type_counts.get("Flora", 0),
            "Mineral": type_counts.get("Mineral", 0),
            "Other": sum(count for name, count in type_counts.items() if name not in {"Animal", "Flora", "Mineral"}),
        },
        "latest_approved_at": latest_approved_at.isoformat() if latest_approved_at else None,
    }


@router.get("/discoveries")
def list_discoveries(
    q: str = Query(default="", max_length=200),
    discovery_type: str = Query(default="", max_length=40),
    location_status: str = Query(default="", max_length=30),
    image_status: str = Query(default="", max_length=30),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    conditions = []
    if discovery_type:
        conditions.append(Discovery.discovery_type == discovery_type)
    if location_status:
        conditions.append(Discovery.location_status == location_status)
    if image_status:
        conditions.append(Discovery.image_status == image_status)

    cleaned_query = " ".join(q.strip().split())
    if cleaned_query:
        wc_match = re.fullmatch(r"WC-[AFMO]-(\d{1,9})", cleaned_query.upper())
        if wc_match:
            conditions.append(Discovery.id == int(wc_match.group(1)))
        elif cleaned_query.isdigit():
            conditions.append(Discovery.id == int(cleaned_query))
        else:
            pattern = f"%{cleaned_query}%"
            conditions.append(or_(
                Discovery.display_name.ilike(pattern),
                Discovery.contributor.ilike(pattern),
                Discovery.owner.ilike(pattern),
                Discovery.ua.ilike(pattern),
                Discovery.message_id.ilike(pattern),
                Discovery.galaxy_name.ilike(pattern),
            ))

    base = select(Discovery)
    count_query = select(func.count()).select_from(Discovery)
    if conditions:
        base = base.where(*conditions)
        count_query = count_query.where(*conditions)

    total = session.scalar(count_query) or 0
    rows = session.scalars(
        base.order_by(Discovery.id.desc()).limit(limit).offset(offset)
    ).all()

    items = []
    for row in rows:
        primary_image = session.scalar(
            select(ImageContribution).where(
                ImageContribution.discovery_id == row.id,
                ImageContribution.status == "approved",
                ImageContribution.is_primary.is_(True),
            )
        )
        items.append(dict(
            serialize_discovery(row),
            primary_image_url=image_delivery_url(primary_image),
        ))

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }


@router.get("/discoveries/{discovery_id}")
def get_discovery(discovery_id: int, session: Session = Depends(get_session)):
    discovery = session.get(Discovery, discovery_id)
    if not discovery:
        raise HTTPException(status_code=404, detail="Wonder record not found.")

    approved_verifications = session.scalar(
        select(func.count()).select_from(LocationVerification).where(
            LocationVerification.discovery_id == discovery_id,
            LocationVerification.status == "approved",
        )
    ) or 0
    pending_verifications = session.scalar(
        select(func.count()).select_from(LocationVerification).where(
            LocationVerification.discovery_id == discovery_id,
            LocationVerification.status == "pending",
        )
    ) or 0

    payload = serialize_discovery(discovery, detail=True)
    approved_images = session.scalars(
        select(ImageContribution).where(
            ImageContribution.discovery_id == discovery_id,
            ImageContribution.status == "approved",
        ).order_by(ImageContribution.is_primary.desc(), ImageContribution.created_at.asc())
    ).all()
    payload["images"] = [{
        "id": image.id,
        "url": image_delivery_url(image),
        "cdn_url": image.public_url,
        "role": image.image_role,
        "caption": image.caption,
        "contributor": image.contributor,
        "width": image.width,
        "height": image.height,
        "is_primary": image.is_primary,
    } for image in approved_images]
    payload["primary_image_url"] = image_delivery_url(next((image for image in approved_images if image.is_primary), approved_images[0] if approved_images else None))
    payload["verification_counts"] = {
        "approved": approved_verifications,
        "pending": pending_verifications,
    }
    return payload
