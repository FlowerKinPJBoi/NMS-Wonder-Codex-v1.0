from __future__ import annotations

from typing import Any


SUPPORTED_FAUNA_ARCHETYPES = {
    "ANTELOPE": ("fauna.antelope", "Slender grazer"),
    "CAT": ("fauna.cat", "Feline predator"),
    "FLOATSPIDER": ("fauna.floatspider", "Floating arachnid"),
    "HERMITCRAB": ("fauna.hermitcrab", "Shelled arthropod"),
    "TREX": ("fauna.trex", "Large bipedal predator"),
    "TRICERATOPS": ("fauna.triceratops", "Horned grazer"),
}

CATEGORY_ARCHETYPES = {
    "Animal": ("fauna.unknown", "Unclassified fauna"),
    "Flora": ("flora.unknown", "Unclassified flora"),
    "Mineral": ("mineral.unknown", "Unclassified mineral"),
}

OTHER_ARCHETYPE = ("other.unknown", "Unclassified Wonder")


def discovery_match_key(record: Any) -> tuple[str, ...]:
    """Return the exact projector identity shared by a discovery and pet match."""
    return tuple(str(getattr(record, field, "") or "") for field in (
        "ua",
        "vp0",
        "vp1",
        "vp2",
        "vp3",
        "vp4",
        "message_id",
    ))


def archetype_metadata(discovery: Any, pet_match: Any | None = None) -> dict[str, str]:
    """Choose a public, allowlisted representative archetype for a catalog record."""
    if getattr(discovery, "discovery_type", "") == "Animal" and pet_match is not None:
        creature_id = str(getattr(pet_match, "creature_id", "") or "").strip().upper()
        supported = SUPPORTED_FAUNA_ARCHETYPES.get(creature_id)
        if supported:
            key, label = supported
            return {
                "archetype_key": key,
                "archetype_label": label,
                "archetype_source": "confirmed_pet_match",
            }

    key, label = CATEGORY_ARCHETYPES.get(
        getattr(discovery, "discovery_type", ""),
        OTHER_ARCHETYPE,
    )
    return {
        "archetype_key": key,
        "archetype_label": label,
        "archetype_source": "category_fallback",
    }
