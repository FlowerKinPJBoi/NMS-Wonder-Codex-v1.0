from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import AssetSighting, AssetSpecimen, AuditEvent
from ..schemas import AssetCatalogUpdate, AssetManifestImport
from ..services.assets import AssetManifestError, asset_wc_id, normalize_manifest, serialize_asset
from ..services.security import require_admin_key

public_router = APIRouter(tags=["assets"])
admin_router = APIRouter(prefix="/admin/assets", tags=["admin-assets"])


def _best_sighting(session: Session, asset_id: int) -> AssetSighting | None:
    return session.scalar(
        select(AssetSighting)
        .where(AssetSighting.asset_id == asset_id, AssetSighting.status.in_(["verified", "pending"]))
        .order_by(AssetSighting.status.desc(), AssetSighting.created_at.asc())
    )


@public_router.get("/asset-types")
def list_asset_types(session: Session = Depends(get_session)):
    rows = session.execute(
        select(AssetSpecimen.asset_type, func.count(AssetSpecimen.id))
        .where(AssetSpecimen.publication_state == "published")
        .group_by(AssetSpecimen.asset_type)
    ).all()
    counts = {str(name): int(count) for name, count in rows}
    return {"items": [{"id": name, "count": counts.get(name, 0)} for name in ["Starship", "Freighter", "Frigate", "Multitool"]]}


@public_router.get("/assets")
def list_assets(
    q: str = Query(default="", max_length=200),
    asset_type: str = Query(default="", max_length=40),
    location_status: str = Query(default="", max_length=30),
    image_status: str = Query(default="", max_length=30),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    conditions = [AssetSpecimen.publication_state == "published"]
    if asset_type:
        conditions.append(AssetSpecimen.asset_type == asset_type)
    if image_status:
        conditions.append(AssetSpecimen.image_status == image_status)
    if location_status == "verified":
        conditions.append(exists().where(and_(AssetSighting.asset_id == AssetSpecimen.id, AssetSighting.status == "verified")))
    elif location_status:
        conditions.append(~exists().where(and_(AssetSighting.asset_id == AssetSpecimen.id, AssetSighting.status == "verified")))

    cleaned = " ".join(q.strip().split())
    if cleaned:
        match = re.fullmatch(r"WC-(?:SH|FR|FG|MT)-(\d{1,9})", cleaned.upper())
        if match:
            conditions.append(AssetSpecimen.id == int(match.group(1)))
        else:
            pattern = f"%{cleaned}%"
            conditions.append(or_(
                AssetSpecimen.display_name.ilike(pattern), AssetSpecimen.asset_key.ilike(pattern),
                AssetSpecimen.source_role.ilike(pattern),
                and_(AssetSpecimen.public_attribution.is_(True), AssetSpecimen.contributor.ilike(pattern)),
            ))

    total = session.scalar(select(func.count()).select_from(AssetSpecimen).where(*conditions)) or 0
    rows = session.scalars(
        select(AssetSpecimen).where(*conditions).order_by(AssetSpecimen.id.desc()).limit(limit).offset(offset)
    ).all()
    items = [serialize_asset(row, _best_sighting(session, row.id)) for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset, "has_more": offset + len(rows) < total}


@public_router.get("/assets/{asset_id}")
def get_asset(asset_id: int, session: Session = Depends(get_session)):
    asset = session.get(AssetSpecimen, asset_id)
    if not asset or asset.publication_state != "published":
        raise HTTPException(status_code=404, detail="Published asset specimen not found.")
    return serialize_asset(asset, _best_sighting(session, asset.id), detail=True)


@admin_router.post("/import")
def import_asset_manifest(
    payload: AssetManifestImport,
    actor: str = Depends(require_admin_key),
    session: Session = Depends(get_session),
):
    try:
        records, skipped = normalize_manifest(payload.manifest)
    except AssetManifestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_name = str(payload.manifest.get("saveName", ""))[:200]
    platform = str(payload.manifest.get("platform", ""))[:40]
    created = updated = 0
    for values in records:
        row = session.scalar(select(AssetSpecimen).where(AssetSpecimen.asset_key == values["asset_key"]))
        if row is None:
            row = AssetSpecimen(
                **values, contributor=payload.contributor, save_name=save_name, platform=platform,
                public_attribution=payload.public_attribution, image_status="needed", reviewer_note="",
            )
            session.add(row)
            created += 1
        else:
            for key in [
                "display_name", "source_role", "source_collection", "source_ordinal", "identity_basis",
                "confidence", "modified_or_special_signal", "delivery_eligibility", "delivery_evidence_status", "fields",
            ]:
                setattr(row, key, values[key])
            row.contributor, row.save_name, row.platform = payload.contributor, save_name, platform
            row.public_attribution = payload.public_attribution
            updated += 1

    session.add(AuditEvent(
        event_type="asset_manifest_imported", actor=actor, batch_id=save_name[:36],
        detail={"created": created, "updated": updated, "skipped": skipped, "schema": payload.manifest.get("schema", "")},
    ))
    session.commit()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped, "review_state": "review"}


@admin_router.get("")
def admin_list_assets(
    publication_state: str = Query(default="review", max_length=30),
    limit: int = Query(default=200, ge=1, le=500),
    actor: str = Depends(require_admin_key),
    session: Session = Depends(get_session),
):
    del actor
    query = select(AssetSpecimen)
    if publication_state != "all":
        query = query.where(AssetSpecimen.publication_state == publication_state)
    rows = session.scalars(query.order_by(AssetSpecimen.created_at.desc()).limit(limit)).all()
    return {"items": [serialize_asset(row, _best_sighting(session, row.id), detail=True, admin=True) for row in rows]}


@admin_router.get("/{asset_id}")
def admin_get_asset(asset_id: int, actor: str = Depends(require_admin_key), session: Session = Depends(get_session)):
    del actor
    asset = session.get(AssetSpecimen, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset specimen not found.")
    return serialize_asset(asset, _best_sighting(session, asset.id), detail=True, admin=True)


@admin_router.patch("/{asset_id}")
def admin_update_asset(
    asset_id: int, changes: AssetCatalogUpdate, actor: str = Depends(require_admin_key),
    session: Session = Depends(get_session),
):
    asset = session.get(AssetSpecimen, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset specimen not found.")
    values = changes.model_dump(exclude_unset=True)
    effective_role = values.get("source_role", asset.source_role)
    if values.get("publication_state") == "published" and effective_role == "unknown":
        raise HTTPException(status_code=400, detail="Classify the asset source role before publishing it.")
    for key, value in values.items():
        setattr(asset, key, value)
    session.add(AuditEvent(
        event_type="asset_specimen_updated", actor=actor, batch_id=str(asset.id),
        detail={"wc_id": asset_wc_id(asset), "fields": sorted(values)},
    ))
    session.commit()
    session.refresh(asset)
    return {"ok": True, "asset": serialize_asset(asset, _best_sighting(session, asset.id), detail=True, admin=True)}
