from __future__ import annotations

from typing import Any

from ..models import Discovery


TYPE_PREFIX = {
    "Animal": "A",
    "Flora": "F",
    "Mineral": "M",
}


def wc_id(discovery: Discovery | int, discovery_type: str | None = None) -> str:
    if isinstance(discovery, Discovery):
        record_id = discovery.id
        kind = discovery.discovery_type
    else:
        record_id = discovery
        kind = discovery_type or "Other"
    prefix = TYPE_PREFIX.get(kind, "O")
    return f"WC-{prefix}-{record_id:06d}"


def display_name(discovery: Discovery) -> str:
    if discovery.display_name:
        return discovery.display_name
    label = {
        "Animal": "Fauna discovery",
        "Flora": "Flora discovery",
        "Mineral": "Mineral discovery",
    }.get(discovery.discovery_type, f"{discovery.discovery_type or 'Wonder'} discovery")
    return f"{label} {wc_id(discovery)}"


def serialize_discovery(discovery: Discovery, *, detail: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": discovery.id,
        "wc_id": wc_id(discovery),
        "display_name": display_name(discovery),
        "custom_display_name": discovery.display_name,
        "discovery_type": discovery.discovery_type,
        "contributor": discovery.contributor,
        "save_name": discovery.save_name,
        "owner": discovery.owner,
        "platform": discovery.platform,
        "created_at": discovery.created_at.isoformat(),
        "updated_at": discovery.updated_at.isoformat() if discovery.updated_at else None,
        "message_id": discovery.message_id,
        "ua": discovery.ua,
        "galaxy_number": discovery.galaxy_number,
        "galaxy_name": discovery.galaxy_name,
        "portal_glyphs": discovery.portal_glyphs,
        "location_status": discovery.location_status,
        "projector_status": discovery.projector_status,
        "image_status": discovery.image_status,
        "catalog_note": discovery.catalog_note,
        "has_location": bool(
            discovery.location_status == "verified"
            and discovery.galaxy_number
            and len(discovery.portal_glyphs or "") == 12
        ),
    }
    if detail:
        item.update({
            "vp0": discovery.vp0,
            "vp1": discovery.vp1,
            "vp2": discovery.vp2,
            "vp3": discovery.vp3,
            "vp4": discovery.vp4,
            "approved_from_batch_id": discovery.approved_from_batch_id,
        })
    return item
