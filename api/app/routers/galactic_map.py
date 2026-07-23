from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, load_only

from ..database import get_session
from ..models import AssetSighting, AssetSpecimen, Discovery, PetDiscoveryMatch
from ..services.archetypes import (
    archetype_metadata,
    build_exact_match_index,
    build_vp1_family_index,
    discovery_match_key,
)
from ..services.assets import asset_wc_id
from ..services.catalog import PUBLIC_HIDDEN_DISCOVERY_TYPES, display_name, wc_id
from ..services.locations import GALAXY_NAMES, decode_portal_coordinates, effective_location


router = APIRouter(tags=["galactic-map"])
ASSET_LANES = {"Starship", "Freighter", "Frigate", "Multitool"}


def _matches_text(values: list[object], query: str) -> bool:
    if not query:
        return True
    needle = query.casefold()
    return any(needle in str(value or "").casefold() for value in values)


@router.get("/map-points")
def list_map_points(
    response: Response,
    galaxy_number: int = Query(default=1, ge=1, le=256),
    catalog_lane: str = Query(default="wonders", max_length=40),
    discovery_type: str = Query(default="", max_length=40),
    fauna_family: str = Query(default="", max_length=120),
    location_quality: str = Query(default="all", pattern="^(all|verified|derived)$"),
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=5000, ge=1, le=5000),
    session: Session = Depends(get_session),
):
    """Return privacy-safe catalog coordinates for the interactive map.

    Discovery coordinates are decoded from confirmed Universal Addresses or
    curated portal routes. Asset coordinates are included only when a
    separately reviewed sighting is verified; an asset seed is never treated
    as location evidence.
    """
    lane = catalog_lane if catalog_lane in ASSET_LANES | {"wonders", "all"} else "wonders"
    # This endpoint contains only public, privacy-safe catalog coordinates. A
    # short shared cache makes common galaxy/filter views fast while keeping
    # newly published evidence visible within a couple of minutes.
    response.headers["Cache-Control"] = "public, max-age=60, s-maxage=120, stale-while-revalidate=300"
    cleaned_query = " ".join(q.strip().split())
    requested_family = fauna_family.strip().upper()
    points: list[dict[str, object]] = []
    available = 0

    if lane in {"wonders", "all"}:
        matches = session.scalars(
            select(PetDiscoveryMatch).options(load_only(
                PetDiscoveryMatch.creature_id,
                PetDiscoveryMatch.creature_type,
                PetDiscoveryMatch.ua,
                PetDiscoveryMatch.vp0,
                PetDiscoveryMatch.vp1,
                PetDiscoveryMatch.vp2,
                PetDiscoveryMatch.vp3,
            ))
        ).all()
        exact_index = build_exact_match_index(matches)
        family_index = build_vp1_family_index(matches)
        query = select(Discovery).where(
            Discovery.discovery_type.notin_(PUBLIC_HIDDEN_DISCOVERY_TYPES)
        ).options(load_only(
            Discovery.id,
            Discovery.discovery_type,
            Discovery.ua,
            Discovery.vp0,
            Discovery.vp1,
            Discovery.vp2,
            Discovery.vp3,
            Discovery.display_name,
            Discovery.galaxy_number,
            Discovery.galaxy_name,
            Discovery.portal_glyphs,
            Discovery.location_status,
        ))
        if discovery_type:
            query = query.where(Discovery.discovery_type == discovery_type)
        if location_quality == "verified":
            query = query.where(Discovery.location_status == "verified")
        rows = session.scalars(query.order_by(Discovery.id.asc())).all()

        for row in rows:
            location = effective_location(
                ua=row.ua,
                galaxy_number=row.galaxy_number,
                galaxy_name=row.galaxy_name,
                portal_glyphs=row.portal_glyphs,
                location_status=row.location_status,
            )
            if location.get("galaxy_number") != galaxy_number or not location.get("has_travel_address"):
                continue
            if location_quality == "all" and location.get("travel_status") not in {"verified", "derived"}:
                continue
            if location_quality != "all" and location.get("travel_status") != location_quality:
                continue
            identity = archetype_metadata(
                row,
                exact_index.get(discovery_match_key(row)),
                family_index.get(row.vp1),
            )
            family_id = str(identity.get("fauna_family_id") or "").upper()
            if requested_family and family_id != requested_family:
                continue
            name = display_name(row)
            record_id = wc_id(row)
            family_label = str(identity.get("fauna_family_label") or "")
            if not _matches_text([record_id, name, row.discovery_type, family_id, family_label], cleaned_query):
                continue
            coordinates = decode_portal_coordinates(location.get("portal_glyphs"))
            if not coordinates:
                continue
            available += 1
            if len(points) >= limit:
                continue
            points.append({
                "key": f"wonder:{row.id}",
                "wc_id": record_id,
                "record_kind": "wonder",
                "record_type": row.discovery_type,
                "display_name": name,
                "family_id": family_id,
                "family_label": family_label,
                "galaxy_number": galaxy_number,
                "galaxy_name": GALAXY_NAMES[galaxy_number] or "",
                "portal_glyphs": location["portal_glyphs"],
                "x": coordinates["x"],
                "y": coordinates["y"],
                "z": coordinates["z"],
                "travel_status": location["travel_status"],
                "record_url": f"record.html?id={row.id}",
            })

    if lane in ASSET_LANES | {"all"} and location_quality != "derived":
        asset_query = (
            select(AssetSpecimen, AssetSighting)
            .join(AssetSighting, AssetSighting.asset_id == AssetSpecimen.id)
            .where(
                AssetSpecimen.publication_state == "published",
                AssetSighting.status == "verified",
                AssetSighting.galaxy_number == galaxy_number,
            )
        )
        if lane in ASSET_LANES:
            asset_query = asset_query.where(AssetSpecimen.asset_type == lane)
        for asset, sighting in session.execute(asset_query.order_by(AssetSpecimen.id.asc())).all():
            fields = asset.fields or {}
            record_id = asset_wc_id(asset)
            name = asset.display_name or f"{asset.asset_type} specimen {record_id}"
            asset_class = str(fields.get("class", ""))
            if not _matches_text([record_id, name, asset.asset_type, asset_class], cleaned_query):
                continue
            coordinates = decode_portal_coordinates(sighting.portal_glyphs)
            if not coordinates:
                continue
            available += 1
            if len(points) >= limit:
                continue
            points.append({
                "key": f"asset:{asset.id}:{sighting.id}",
                "wc_id": record_id,
                "record_kind": "asset",
                "record_type": asset.asset_type,
                "display_name": name,
                "family_id": "",
                "family_label": asset_class,
                "galaxy_number": galaxy_number,
                "galaxy_name": sighting.galaxy_name or GALAXY_NAMES[galaxy_number] or "",
                "portal_glyphs": sighting.portal_glyphs,
                "x": coordinates["x"],
                "y": coordinates["y"],
                "z": coordinates["z"],
                "travel_status": "verified",
                "record_url": f"asset.html?id={asset.id}",
            })

    return {
        "items": points,
        "returned": len(points),
        "available": available,
        "truncated": available > len(points),
        "galaxy_number": galaxy_number,
        "galaxy_name": GALAXY_NAMES[galaxy_number],
        "catalog_lane": lane,
        "coordinate_model": "portal_signed_voxel_v1",
        "location_policy": "UA/curated routes for Wonders; verified sightings only for assets; seeds are never coordinates.",
    }
