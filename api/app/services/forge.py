from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


MATCHED_IMAGE_LABEL = "Evidence-matched Forge reconstruction — verify color and lighting in game."
FORGE_CATALOG_VERSION = "wonder-forge-v0.1.32-precision-binding"
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


SELECTOR_FIELDS = {
    "forge_selector_fingerprints": ("forge_selector_fingerprint",),
    "visual_profile_fingerprints": ("visual_profile_fingerprint",),
    "identity_fingerprints": ("identity_fingerprint", "identityFingerprint"),
    "record_hashes": ("record_hash",),
    "message_ids": ("message_id",),
    "wc_ids": ("wc_id",),
}


def _record_value(record: Any, aliases: tuple[str, ...]) -> str:
    fields = getattr(record, "fields", None)
    for alias in aliases:
        if isinstance(record, dict) and record.get(alias) not in (None, ""):
            return str(record[alias]).strip()
        value = getattr(record, alias, None)
        if value not in (None, ""):
            return str(value).strip()
        if isinstance(fields, dict) and fields.get(alias) not in (None, ""):
            return str(fields[alias]).strip()
    return ""


def _selector_matches(entry: dict[str, Any], record: Any, extra: dict[str, Any] | None = None) -> bool:
    selectors = entry.get("record_selectors")
    if not isinstance(selectors, dict) or not selectors:
        return False
    extra = extra or {}
    for selector_name, aliases in SELECTOR_FIELDS.items():
        expected = selectors.get(selector_name)
        if not isinstance(expected, list) or not expected:
            continue
        actual = str(extra.get(aliases[0], "") or _record_value(record, aliases)).strip().upper()
        if actual and actual in {str(value).strip().upper() for value in expected}:
            return True
    return False


def _selector_forms(
    record: Any,
    forms: tuple[dict[str, Any], ...],
    extra: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    return tuple(entry for entry in forms if _selector_matches(entry, record, extra))


def _metadata(
    forms: tuple[dict[str, Any], ...],
    *,
    match_basis: str,
    match_label: str,
) -> dict[str, Any]:
    if not forms:
        return {}
    highest_priority = max(int(entry.get("record_match_priority", 0)) for entry in forms)
    winners = tuple(
        entry for entry in forms
        if int(entry.get("record_match_priority", 0)) == highest_priority
    )
    if len(winners) != 1:
        return {}
    entry = winners[0]
    return {
        "forge_catalog_version": FORGE_CATALOG_VERSION,
        "forge_image_url": f"/{entry['image_url'].lstrip('/')}",
        "forge_form_id": entry["id"],
        "forge_form_name": entry["form_name"],
        "forge_family_id": entry["family_id"],
        "forge_family_display": entry["family_display"],
        "forge_category_id": entry["category_id"],
        "forge_image_status": "evidence_matched_reconstruction",
        "forge_match_basis": match_basis,
        "forge_match_label": match_label,
        "forge_catalog_class": entry["evidence_class"],
        "forge_authenticity_status": "EVIDENCE_MATCHED_RECONSTRUCTION",
        "forge_exact_specimen": False,
        "forge_display_label": entry.get("display_label", MATCHED_IMAGE_LABEL),
        "forge_selection_basis": "explicit_catalog_record_selector",
        "forge_match_precision": entry.get("match_precision", "visual_variant"),
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


def discovery_selector_fingerprint(discovery: Any, discovery_type: str = "") -> str:
    """Build a privacy-safe key for one complete DiscoveryData visual identity."""
    values = tuple(
        _canonical_hex(getattr(discovery, field, ""), prefer_hex=True)
        for field in ("ua", "vp0", "vp1", "vp2", "vp3")
    )
    if not all(values[:3]):
        return ""
    identity = "|".join((str(discovery_type or "").strip().upper(), *values))
    return f"WCF-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24].upper()}"


def _planet_metadata(discovery: Any) -> dict[str, Any]:
    try:
        vp1_low = _integer_value(getattr(discovery, "vp1", "")) & 0xFFFF
    except ValueError:
        return {}
    family = PLANET_FAMILIES.get(vp1_low)
    if not family:
        return {}

    family_name, _ = family
    exact_giant = _planet_identity_hash(discovery) in EXACT_GIANT_PLANET_HASHES
    if vp1_low == 15:
        size_class = "Gas Giant"
        size_status = "confirmed_gas_giant_family"
        radius = 24
    elif exact_giant:
        size_class = "Giant"
        size_status = "exact_joined_giant_base"
        radius = 24
    else:
        size_class = "Standard"
        size_status = "representative_size_unknown_in_discovery_data"
        radius = 10

    family_id = re.sub(r"[^A-Z0-9]+", "_", family_name.upper()).strip("_")
    captured_name = str(getattr(discovery, "display_name", "") or "").strip()
    return {
        "forge_selector_fingerprint": discovery_selector_fingerprint(discovery, "Planet"),
        "forge_match_status": "awaiting_exact_visual_binding",
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
    *,
    visual_profile_fingerprint: str = "",
    descriptor_evidence_status: str = "",
) -> dict[str, Any]:
    """Return only visual art explicitly bound to this record's evidence."""
    selector_fingerprint = discovery_selector_fingerprint(discovery, discovery_type)
    selector_metadata = {
        "forge_selector_fingerprint": selector_fingerprint,
        "forge_match_status": "awaiting_exact_visual_binding",
    }
    if discovery_type == "Planet":
        metadata = _planet_metadata(discovery)
        forms = _forms(category="planets")
        matched = _selector_forms(discovery, forms, selector_metadata)
        metadata.update(_metadata(
            matched,
            match_basis="exact_discovery_selector",
            match_label="Exact DiscoveryData visual identity",
        ))
        if "forge_image_url" in metadata:
            metadata["forge_match_status"] = "matched"
        return metadata

    if discovery_type == "Animal":
        if identity_source not in {"exact_pet_match", "confirmed_vp1_mapping"}:
            return selector_metadata
        forms = _forms(
            category="fauna",
            family_id=str(family_id or "").upper(),
        )
        extra = dict(selector_metadata)
        if descriptor_evidence_status == "observed_save_tokens":
            extra["visual_profile_fingerprint"] = visual_profile_fingerprint
        matched = _selector_forms(discovery, forms, extra)
        metadata = _metadata(
            matched,
            match_basis="descriptor_or_exact_discovery_selector",
            match_label="Descriptor-bound visual variant",
        )
        selector_metadata.update(metadata)
        if metadata:
            selector_metadata["forge_match_status"] = "matched"
        return selector_metadata

    category = {"Flora": "flora", "Mineral": "minerals"}.get(discovery_type)
    if not category:
        return selector_metadata
    forms = _forms(category=category)
    matched = _selector_forms(discovery, forms, selector_metadata)
    metadata = _metadata(
        matched,
        match_basis="exact_discovery_selector",
        match_label=f"Exact {discovery_type} DiscoveryData visual identity",
    )
    selector_metadata.update(metadata)
    if metadata:
        selector_metadata["forge_match_status"] = "matched"
    return selector_metadata


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
    forms = _forms(category=category)
    matched = _selector_forms(asset, forms)
    return _metadata(
        matched,
        match_basis="exact_asset_identity_selector",
        match_label=f"Exact {str(getattr(asset, 'asset_type', '')).lower()} visual identity",
    )
