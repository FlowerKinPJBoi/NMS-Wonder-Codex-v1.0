from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPRESENTATIVE_IMAGE_LABEL = "Representative family image — not this exact specimen."
FORGE_CATALOG_VERSION = "wonder-forge-v0.1.18"
CATALOG_PATH = Path(__file__).resolve().parents[3] / "assets" / "forge" / "forge-catalog.json"


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


def forge_representative_metadata(
    discovery: Any,
    family_id: str,
    identity_source: str,
    discovery_type: str,
) -> dict[str, Any]:
    """Return evidence-safe representative art for a discovery."""
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
    category = {"Frigate": "frigates", "Multitool": "multitools"}.get(
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
