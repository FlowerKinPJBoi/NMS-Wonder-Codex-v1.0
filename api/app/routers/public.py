from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from ..database import get_session
from ..models import Discovery, PetDiscoveryMatch, SubmissionBatch

router = APIRouter(tags=["public"])


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
