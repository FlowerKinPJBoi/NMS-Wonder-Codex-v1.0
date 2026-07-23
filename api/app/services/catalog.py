from __future__ import annotations

from typing import Any

from ..models import Discovery
from .locations import effective_location


TYPE_PREFIX = {
    "Animal": "A",
    "Flora": "F",
    "Mineral": "M",
}

# These records remain in the database and contribution pipeline but are not
# standalone specimens in the public-facing catalog or cluster map.
PUBLIC_HIDDEN_DISCOVERY_TYPES = ("SolarSystem",)


def is_publicly_listed_discovery_type(discovery_type: str) -> bool:
    return discovery_type not in PUBLIC_HIDDEN_DISCOVERY_TYPES


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


def public_contributor(name: str, is_public: bool) -> str:
    return name if is_public else "Anonymous Contributor"


def serialize_discovery(discovery: Discovery, *, detail: bool = False) -> dict[str, Any]:
    location = effective_location(
        ua=discovery.ua,
        galaxy_number=discovery.galaxy_number,
        galaxy_name=discovery.galaxy_name,
        portal_glyphs=discovery.portal_glyphs,
        location_status=discovery.location_status,
    )

    item: dict[str, Any] = {
        "id": discovery.id,
        "wc_id": wc_id(discovery),
        "display_name": display_name(discovery),
        "custom_display_name": discovery.display_name,
        "discovery_type": discovery.discovery_type,
        "contributor": public_contributor(discovery.contributor, discovery.public_attribution),
        "save_name": discovery.save_name if discovery.public_attribution else "",
        "public_attribution": discovery.public_attribution,
        "owner": discovery.owner if discovery.public_attribution else "",
        "platform": discovery.platform,
        "created_at": discovery.created_at.isoformat(),
        "updated_at": discovery.updated_at.isoformat() if discovery.updated_at else None,
        "message_id": discovery.message_id,
        "ua": discovery.ua,
        "ua_normalized": location["ua_decoded"]["ua_normalized"] if location["ua_decoded"] else "",
        "galaxy_number": location["galaxy_number"],
        "galaxy_name": location["galaxy_name"],
        "portal_glyphs": location["portal_glyphs"],
        "location_status": discovery.location_status,
        "travel_status": location["travel_status"],
        "location_source": location["location_source"],
        "location_is_derived": location["location_is_derived"],
        "location_conflict": location["location_conflict"],
        "projector_status": discovery.projector_status,
        "image_status": discovery.image_status,
        "catalog_note": discovery.catalog_note,
        "has_location": location["has_location"],
        "has_travel_address": location["has_travel_address"],
    }
    if location["ua_decoded"]:
        item.update({
            "reality_index": location["ua_decoded"]["reality_index"],
            "planet_index": location["ua_decoded"]["planet_index"],
            "solar_system_index": location["ua_decoded"]["solar_system_index"],
            "location_derivation_method": location["ua_decoded"]["location_derivation_method"],
        })
    else:
        item.update({
            "reality_index": None,
            "planet_index": None,
            "solar_system_index": None,
            "location_derivation_method": "",
        })

    if detail:
        item.update({
            "vp0": discovery.vp0,
            "vp1": discovery.vp1,
            "vp2": discovery.vp2,
            "vp3": discovery.vp3,
            "vp4": discovery.vp4,
            "approved_from_batch_id": discovery.approved_from_batch_id,
            "catalog_galaxy_number": discovery.galaxy_number,
            "catalog_galaxy_name": discovery.galaxy_name,
            "catalog_portal_glyphs": discovery.portal_glyphs,
        })
    return item
