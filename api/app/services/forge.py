from __future__ import annotations

import hashlib
from typing import Any


REPRESENTATIVE_IMAGE_LABEL = "Representative family image — not this exact specimen."
FORGE_CATALOG_VERSION = "wonder-forge-v1.18"


# Only natural forms marked VERIFIED_REFERENCE_FORM in the returned Forge
# manifests may be used on discovery records. Synthetic variants stay in the
# public Forge gallery and never enter this record-image pool.
VERIFIED_FAMILY_FORMS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "BLOB": (
        ("clean-wild-blob", "Clean Wild Blob", "/assets/forge/verified/blob/clean-wild-blob.webp"),
    ),
    "FLOATSPIDER": (
        ("crab-floater", "Crab Floater", "/assets/forge/verified/floatspider/crab-floater.webp"),
        ("jelly-floater", "Jelly Floater", "/assets/forge/verified/floatspider/jelly-floater.webp"),
        ("mantis-floater", "Mantis Floater", "/assets/forge/verified/floatspider/mantis-floater.webp"),
        ("mushroom-b11-floater", "Mushroom B11 Floater", "/assets/forge/verified/floatspider/mushroom-b11-floater.webp"),
        ("mushroom-b12-floater", "Mushroom B12 Floater", "/assets/forge/verified/floatspider/mushroom-b12-floater.webp"),
        ("stalk-eyed-floater", "Stalk-Eyed Floater", "/assets/forge/verified/floatspider/stalk-eyed-floater.webp"),
    ),
    "HERMITCRAB": (
        ("shell-01", "Shell-Less Wild Crab", "/assets/forge/verified/hermitcrab/shell-01.webp"),
        ("shell-02", "Hermit Shell 02", "/assets/forge/verified/hermitcrab/shell-02.webp"),
        ("shell-03", "Hermit Shell 03", "/assets/forge/verified/hermitcrab/shell-03.webp"),
        ("shell-04", "Hermit Shell 04", "/assets/forge/verified/hermitcrab/shell-04.webp"),
        ("shell-05", "Hermit Shell 05", "/assets/forge/verified/hermitcrab/shell-05.webp"),
        ("shell-06", "Hermit Shell 06", "/assets/forge/verified/hermitcrab/shell-06.webp"),
    ),
    "TREX": (
        ("bird-rex", "Bird Rex", "/assets/forge/verified/trex/bird-rex.webp"),
        ("classic-trex", "Classic T-Rex", "/assets/forge/verified/trex/classic-trex.webp"),
        ("croc-rex", "Croc Rex", "/assets/forge/verified/trex/croc-rex.webp"),
        ("rat-rex", "Rat Rex", "/assets/forge/verified/trex/rat-rex.webp"),
        ("rhino-rex", "Rhino Rex", "/assets/forge/verified/trex/rhino-rex.webp"),
    ),
    "TRICERATOPS": (
        ("classic-triceratops", "Classic Triceratops", "/assets/forge/verified/triceratops/classic-triceratops.webp"),
        ("diplo", "Diplo", "/assets/forge/verified/triceratops/diplo.webp"),
        ("rhino", "Rhino", "/assets/forge/verified/triceratops/rhino.webp"),
        ("tapir", "Tapir", "/assets/forge/verified/triceratops/tapir.webp"),
        ("turtle", "Turtle", "/assets/forge/verified/triceratops/turtle.webp"),
    ),
    "WALKINGBUILDING": (
        ("building-01", "Walking Building 01", "/assets/forge/verified/walkingbuilding/building-01.webp"),
        ("building-02a", "Walking Building 02A", "/assets/forge/verified/walkingbuilding/building-02a.webp"),
        ("building-02b", "Walking Building 02B", "/assets/forge/verified/walkingbuilding/building-02b.webp"),
        ("building-04", "Walking Building 04", "/assets/forge/verified/walkingbuilding/building-04.webp"),
        ("building-05", "Walking Building 05", "/assets/forge/verified/walkingbuilding/building-05.webp"),
        ("building-06", "Walking Building 06", "/assets/forge/verified/walkingbuilding/building-06.webp"),
        ("building-07", "Walking Building 07", "/assets/forge/verified/walkingbuilding/building-07.webp"),
    ),
}


def _stable_form_index(discovery: Any, form_count: int) -> int:
    """Select stable family art without exposing or claiming to decode VP0."""
    individual_signal = str(getattr(discovery, "vp0", "") or "").strip()
    fallback_signal = str(
        getattr(discovery, "record_hash", "")
        or getattr(discovery, "message_id", "")
        or getattr(discovery, "id", "")
    ).strip()
    digest = hashlib.blake2s(
        f"wonder-forge:family-art:{individual_signal or fallback_signal}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big") % form_count


def forge_representative_metadata(
    discovery: Any,
    family_id: str,
    identity_source: str,
) -> dict[str, Any]:
    """Return evidence-safe representative art for a confirmed fauna family."""
    forms = VERIFIED_FAMILY_FORMS.get(str(family_id or "").upper())
    if not forms or identity_source not in {"exact_pet_match", "confirmed_vp1_mapping"}:
        return {}

    form_id, form_name, image_url = forms[_stable_form_index(discovery, len(forms))]
    match_label = (
        "Exact PetData family match"
        if identity_source == "exact_pet_match"
        else "Confirmed VP1 family mapping"
    )
    return {
        "forge_catalog_version": FORGE_CATALOG_VERSION,
        "forge_image_url": image_url,
        "forge_form_id": form_id,
        "forge_form_name": form_name,
        "forge_family_id": str(family_id).upper(),
        "forge_image_status": "representative_family",
        "forge_match_basis": identity_source,
        "forge_match_label": match_label,
        "forge_catalog_class": "verified_natural_wild_form",
        "forge_authenticity_status": "VERIFIED_REFERENCE_FORM",
        "forge_exact_specimen": False,
        "forge_display_label": REPRESENTATIVE_IMAGE_LABEL,
        "forge_selection_basis": "deterministic_vp0_family_pool",
    }
