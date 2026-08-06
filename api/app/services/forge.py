from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPRESENTATIVE_IMAGE_LABEL = "Representative family image — not this exact specimen."
PLANET_REPRESENTATIVE_LABEL = "Representative family hologram — not this exact planet."
FORGE_CATALOG_VERSION = "wonder-forge-v0.1.32-spacecraft"
CATALOG_PATH = Path(__file__).resolve().parents[3] / "assets" / "forge" / "forge-catalog.json"

PLANET_FAMILIES = {
    0: ("Lush", "00-lush"),
    1: ("Toxic", "01-toxic"),
    2: ("Scorched", "02-scorched"),
    3: ("Radioactive", "03-radioactive"),
    4: ("Frozen", "04-frozen"),
    5: ("Barren", "05-barren"),
    6: ("Dead/Airless", "06-dead-airless"),
    7: ("Weird", "07-weird"),
    8: ("Red", "08-red"),
    9: ("Green", "09-green"),
    10: ("Blue", "10-blue"),
    11: ("Test", "11-test"),
    12: ("Swamp", "12-swamp"),
    13: ("Lava", "13-lava"),
    14: ("Waterworld", "14-waterworld"),
    15: ("Gas Giant", "15-gasgiant"),
}

# These privacy-safe digests are the four exact Planet DiscoveryData records
# joined to explicitly named Giant player bases by Planet Linker v0.1.7.
EXACT_GIANT_PLANET_HASHES = {
    "78c8fbf22717420328a8cbff",
    "1049d4d737b6c5c52635f596",
    "b82c24f769cef182512e9896",
    "9df2813f6ae37434645769fa",
}


def _catalog_entries() -> tuple[dict[str, Any], ...]:
    try:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    return tuple(
        entry for entry in payload.get("entries", [])
        if isinstance(entry, dict)
        and entry.get("record_eligible") is True
        and entry.get("exact_specimen") is False
    )


CATALOG_ENTRIES = _catalog_entries()


def _forms(*, category: str, family_id: str = "", match_scope: str = "") -> tuple[dict[str, Any], ...]:
    return tuple(
        entry for entry in CATALOG_ENTRIES
        if entry.get("category_id") == category
        and (not family_id or str(entry.get("family_id", "")).upper() == family_id.upper())
        and (not match_scope or entry.get("match_scope") == match_scope)
    )


def _stable_form_index(record: Any, form_count: int, namespace: str) -> int:
    """Select stable representative art without claiming to decode an individual."""
    signals = (
        getattr(record, "vp1", ""),
        getattr(record, "vp0", ""),
        getattr(record, "record_hash", ""),
        getattr(record, "asset_key", ""),
        getattr(record, "message_id", ""),
        getattr(record, "id", ""),
    )
    stable_signal = next((str(value).strip() for value in signals if str(value or "").strip()), "wonder")
    digest = hashlib.blake2s(
        f"wonder-forge:{namespace}:{stable_signal}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big") % form_count


def _metadata(
    record: Any,
    forms: tuple[dict[str, Any], ...],
    *,
    namespace: str,
    match_basis: str,
    match_label: str,
) -> dict[str, Any]:
    if not forms:
        return {}
    entry = forms[_stable_form_index(record, len(forms), namespace)]
    return {
        "forge_catalog_version": FORGE_CATALOG_VERSION,
        "forge_image_url": f"/{entry['image_url'].lstrip('/')}",
        "forge_form_id": entry["id"],
        "forge_form_name": entry["form_name"],
        "forge_family_id": entry["family_id"],
        "forge_family_display": entry["family_display"],
        "forge_category_id": entry["category_id"],
        "forge_image_status": "representative_family",
        "forge_match_basis": match_basis,
        "forge_match_label": match_label,
        "forge_catalog_class": entry["evidence_class"],
        "forge_authenticity_status": "APPROVED_REPRESENTATIVE",
        "forge_exact_specimen": False,
        "forge_display_label": entry["display_label"],
        "forge_selection_basis": "deterministic_evidence_safe_pool",
        "forge_ringless": entry.get("ringless") is True,
    }


def _integer_value(value: Any, *, prefer_hex: bool = False) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty numeric value")
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text, 16 if prefer_hex or re.search(r"[a-f]", text, re.IGNORECASE) else 10)


def _canonical_hex(value: Any, *, prefer_hex: bool = False) -> str:
    try:
        return hex(_integer_value(value, prefer_hex=prefer_hex))
    except ValueError:
        return str(value or "").strip().lower()


def _planet_identity_hash(discovery: Any) -> str:
    identity = "|".join((
        _canonical_hex(getattr(discovery, "ua", ""), prefer_hex=True),
        _canonical_hex(getattr(discovery, "vp0", ""), prefer_hex=True),
        _canonical_hex(getattr(discovery, "vp1", "")),
    ))
    if not all(identity.split("|")):
        return ""
    return hashlib.blake2s(identity.encode("utf-8"), digest_size=12).hexdigest()


def _planet_metadata(discovery: Any) -> dict[str, Any]:
    try:
        vp1_low = _integer_value(getattr(discovery, "vp1", "")) & 0xFFFF
    except ValueError:
        return {}
    family = PLANET_FAMILIES.get(vp1_low)
    if not family:
        return {}

    family_name, file_stem = family
    exact_giant = _planet_identity_hash(discovery) in EXACT_GIANT_PLANET_HASHES
    if vp1_low == 15:
        size_class = "Gas Giant"
        file_name = f"{file_stem}-gas-giant.svg"
        size_status = "confirmed_gas_giant_family"
        match_basis = "confirmed_vp1_gas_giant_family"
        radius = 24
    elif exact_giant:
        size_class = "Giant"
        file_name = f"{file_stem}-giant.svg"
        size_status = "exact_joined_giant_base"
        match_basis = "exact_giant_base_planet_join"
        radius = 24
    else:
        size_class = "Standard"
        file_name = f"{file_stem}-standard.svg"
        size_status = "representative_size_unknown_in_discovery_data"
        match_basis = "confirmed_vp1_planet_family"
        radius = 10

    family_id = re.sub(r"[^A-Z0-9]+", "_", family_name.upper()).strip("_")
    captured_name = str(getattr(discovery, "display_name", "") or "").strip()
    return {
        "forge_catalog_version": FORGE_CATALOG_VERSION,
        "forge_image_url": f"/assets/planet-holograms/{file_name}",
        "forge_form_id": f"planet-hologram-{vp1_low:02d}-{size_class.lower().replace(' ', '-')}",
        "forge_form_name": f"{family_name} · {size_class}",
        "forge_family_id": family_id,
        "forge_family_display": family_name,
        "forge_category_id": "planets",
        "forge_image_status": "representative_family",
        "forge_match_basis": match_basis,
        "forge_match_label": (
            "Exact Giant base-to-Planet join"
            if exact_giant
            else "Confirmed VP1 planet family"
        ),
        "forge_catalog_class": "approved_representative_hologram",
        "forge_authenticity_status": "APPROVED_REPRESENTATIVE",
        "forge_exact_specimen": False,
        "forge_display_label": PLANET_REPRESENTATIVE_LABEL,
        "forge_selection_basis": size_status,
        "forge_ringless": True,
        "planet_family_id": family_id,
        "planet_biome_family": family_name,
        "planet_size_class": size_class,
        "planet_size_status": size_status,
        "planet_hologram_radius": radius,
        "planet_name_status": "captured" if captured_name else "generated_name_capture_needed",
        "planet_name_label": (
            f"Captured name: {captured_name}"
            if captured_name
            else "Generated in-game name still needs visual capture"
        ),
        "wonder_family_label": f"{family_name} planet family",
        "wonder_family_source": "confirmed_vp1_planet_family",
        "wonder_individual_name_status": "captured" if captured_name else "encoded_not_decoded",
        "wonder_individual_signal_label": (
            f"Captured in-game name: {captured_name}"
            if captured_name
            else "Generated in-game name still needs visual capture"
        ),
    }


def forge_representative_metadata(
    discovery: Any,
    family_id: str,
    identity_source: str,
    discovery_type: str,
) -> dict[str, Any]:
    """Return evidence-safe representative art for a discovery."""
    if discovery_type == "Planet":
        return _planet_metadata(discovery)

    if discovery_type == "Animal":
        if identity_source not in {"exact_pet_match", "confirmed_vp1_mapping"}:
            return {}
        forms = _forms(
            category="fauna",
            family_id=str(family_id or "").upper(),
            match_scope="confirmed_family",
        )
        return _metadata(
            discovery,
            forms,
            namespace=f"fauna:{family_id}",
            match_basis=identity_source,
            match_label=(
                "Exact PetData family match"
                if identity_source == "exact_pet_match"
                else "Confirmed VP1 family mapping"
            ),
        )

    category = {"Flora": "flora", "Mineral": "minerals"}.get(discovery_type)
    if not category:
        return {}
    forms = _forms(category=category, match_scope="stable_category_family_signal")
    return _metadata(
        discovery,
        forms,
        namespace=f"{category}:vp1-family",
        match_basis="vp1_family_signal",
        match_label=f"Stable {discovery_type.lower()} family signal",
    )


def forge_asset_representative_metadata(asset: Any) -> dict[str, Any]:
    category = {
        "Starship": "starships",
        "Freighter": "freighters",
        "Frigate": "frigates",
        "Multitool": "multitools",
    }.get(
        str(getattr(asset, "asset_type", "") or "")
    )
    if not category:
        return {}
    forms = _forms(category=category, match_scope="stable_asset_type")
    return _metadata(
        asset,
        forms,
        namespace=f"asset:{category}",
        match_basis="procedural_asset_identity",
        match_label=f"Stable {str(getattr(asset, 'asset_type', '')).lower()} identity",
    )
