from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from typing import Any, Iterable

from .descriptors import descriptor_profile


SUPPORTED_FAUNA_ARCHETYPES = {
    "ANTELOPE": ("fauna.antelope", "Slender grazer"),
    "BLOB": ("fauna.blob", "Gelatinous blob"),
    "BONECOW": ("fauna.bonecow", "Skeletal grazer"),
    "CAT": ("fauna.cat", "Feline predator"),
    "COW": ("fauna.cow", "Armored grazer"),
    "FLOATSPIDER": ("fauna.floatspider", "Floating arachnid"),
    "FLYINGBEETLE": ("fauna.flyingbeetle", "Flying beetle"),
    "GRUNT": ("fauna.grunt", "Primate-like fauna"),
    "HERMITCRAB": ("fauna.hermitcrab", "Shelled arthropod"),
    "LARGEBUTTERFLY": ("fauna.largebutterfly", "Large winged insect"),
    "PROTOFLYER": ("fauna.protoflyer", "Proto flyer"),
    "ROBOTANTELOPE": ("fauna.robotantelope", "Mechanical grazer"),
    "SIXLEGCOW": ("fauna.sixlegcow", "Six-legged grazer"),
    "SPIDER": ("fauna.spider", "Ground arachnid"),
    "STRIDER": ("fauna.strider", "Tall strider"),
    "TREX": ("fauna.trex", "Large bipedal predator"),
    "TRICERATOPS": ("fauna.triceratops", "Horned grazer"),
    "TWOLEGANTELOPE": ("fauna.twolegantelope", "Bipedal grazer"),
    "WALKINGBUILDING": ("fauna.walkingbuilding", "Walking construct"),
    "WEIRDFLOAT": ("fauna.weirdfloat", "Crystalline floater"),
}

FAUNA_FAMILY_LABELS = {
    "ANTELOPE": "Antelope",
    "BLOB": "Blob",
    "BONECOW": "Bone Cow",
    "CAT": "Cat",
    "COW": "Cow",
    "FLOATSPIDER": "Float Spider",
    "FLYINGBEETLE": "Flying Beetle",
    "GRUNT": "Grunt",
    "HERMITCRAB": "Hermit Crab",
    "LARGEBUTTERFLY": "Large Butterfly",
    "PLANTCAT": "Plant Cat",
    "PROTOFLYER": "Proto Flyer",
    "ROBOTANTELOPE": "Robot Antelope",
    "SIXLEGCOW": "Six-Leg Cow",
    "SPIDER": "Spider",
    "STRIDER": "Strider",
    "TREX": "T-Rex",
    "TRICERATOPS": "Triceratops",
    "TWOLEGANTELOPE": "Two-Leg Antelope",
    "WALKINGBUILDING": "Walking Building",
    "WEIRDFLOAT": "Weird Float",
}

CATEGORY_ARCHETYPES = {
    "Animal": ("fauna.unknown", "Unclassified fauna"),
    "Flora": ("flora.unknown", "Unclassified flora"),
    "Mineral": ("mineral.unknown", "Unclassified mineral"),
}

OTHER_ARCHETYPE = ("other.unknown", "Unclassified Wonder")

IDENTITY_MODEL_VERSION = "projector-identity-v1"


def _signal_reference(discovery_type: str, role: str, value: Any) -> str:
    """Create a stable public reference without exposing the underlying VP value."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return ""
    prefix = {"Animal": "A", "Flora": "F", "Mineral": "M"}.get(discovery_type, "W")
    digest = hashlib.blake2s(
        f"wonder-codex:{role}:{normalized}".encode("utf-8"),
        digest_size=3,
    ).hexdigest().upper()
    return f"{prefix}-{digest}"


def normalize_creature_id(value: Any) -> str:
    cleaned = str(value or "").strip().lstrip("^").upper()
    return cleaned if re.fullmatch(r"[A-Z0-9_]{1,120}", cleaned) else ""


def family_label(creature_id: str) -> str:
    normalized = normalize_creature_id(creature_id)
    if not normalized:
        return ""
    if normalized in FAUNA_FAMILY_LABELS:
        return FAUNA_FAMILY_LABELS[normalized]
    return normalized.replace("_", " ").title()


def family_vp1s(
    vp1_index: dict[str, dict[str, str | int]],
    query: str,
    *,
    exact: bool,
) -> list[str]:
    """Find mapped VP1 values by friendly or technical family name."""
    needle = re.sub(r"[^A-Z0-9]+", "", query.upper())
    if not needle:
        return []

    matches = []
    for vp1, evidence in vp1_index.items():
        family_id = re.sub(r"[^A-Z0-9]+", "", str(evidence.get("creature_id", "")).upper())
        label = re.sub(r"[^A-Z0-9]+", "", str(evidence.get("family_label", "")).upper())
        is_match = needle in {family_id, label} if exact else needle in family_id or needle in label
        if is_match:
            matches.append(vp1)
    return matches


def discovery_match_key(record: Any) -> tuple[str, ...]:
    """Return the exact key used by the importer to pair PetData and DiscoveryData."""
    return tuple(str(getattr(record, field, "") or "") for field in (
        "ua",
        "vp0",
        "vp2",
        "vp3",
    ))


def build_exact_match_index(pet_matches: Iterable[Any]) -> dict[tuple[str, ...], Any]:
    grouped: dict[tuple[str, ...], list[Any]] = defaultdict(list)
    for match in pet_matches:
        key = discovery_match_key(match)
        if all(key) and normalize_creature_id(getattr(match, "creature_id", "")):
            grouped[key].append(match)

    exact: dict[tuple[str, ...], Any] = {}
    for key, matches in grouped.items():
        families = {normalize_creature_id(getattr(match, "creature_id", "")) for match in matches}
        if len(families) == 1:
            exact[key] = next(
                (match for match in matches if str(getattr(match, "creature_type", "") or "").strip()),
                matches[0],
            )
    return exact


def build_vp1_family_index(pet_matches: Iterable[Any]) -> dict[str, dict[str, str | int]]:
    """Keep only VP1 values whose approved PetData evidence resolves to one family."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for match in pet_matches:
        vp1 = str(getattr(match, "vp1", "") or "").strip()
        creature_id = normalize_creature_id(getattr(match, "creature_id", ""))
        if vp1 and creature_id:
            grouped[vp1].append(creature_id)

    index: dict[str, dict[str, str | int]] = {}
    for vp1, creature_ids in grouped.items():
        unique = set(creature_ids)
        if len(unique) != 1:
            continue
        creature_id = unique.pop()
        index[vp1] = {
            "creature_id": creature_id,
            "family_label": family_label(creature_id),
            "evidence_count": len(creature_ids),
        }
    return index


def archetype_metadata(
    discovery: Any,
    pet_match: Any | None = None,
    vp1_family: dict[str, str | int] | None = None,
) -> dict[str, Any]:
    """Attach evidence-safe family identity and representative artwork metadata."""
    discovery_type = str(getattr(discovery, "discovery_type", "") or "")
    family_id = ""
    behavior = ""
    identity_source = ""
    identity_label = ""
    evidence_count = 0

    if discovery_type == "Animal" and pet_match is not None:
        family_id = normalize_creature_id(getattr(pet_match, "creature_id", ""))
        behavior = str(getattr(pet_match, "creature_type", "") or "").strip().lstrip("^")
        if family_id:
            identity_source = "exact_pet_match"
            identity_label = "Exact PetData match"
            evidence_count = int((vp1_family or {}).get("evidence_count", 1))
    elif discovery_type == "Animal" and vp1_family:
        family_id = normalize_creature_id(vp1_family.get("creature_id", ""))
        if family_id:
            identity_source = "confirmed_vp1_mapping"
            identity_label = "Confirmed VP1 family mapping"
            evidence_count = int(vp1_family.get("evidence_count", 0))

    family_reference = _signal_reference(discovery_type, "family-vp1", getattr(discovery, "vp1", ""))
    individual_reference = _signal_reference(discovery_type, "individual-vp0", getattr(discovery, "vp0", ""))
    captured_name = str(getattr(discovery, "display_name", "") or "").strip()

    supported = SUPPORTED_FAUNA_ARCHETYPES.get(family_id)
    if supported:
        archetype_key, archetype_label = supported
        archetype_source = "confirmed_pet_match" if identity_source == "exact_pet_match" else "confirmed_vp1_mapping"
    else:
        archetype_key, archetype_label = CATEGORY_ARCHETYPES.get(discovery_type, OTHER_ARCHETYPE)
        if family_reference and discovery_type in {"Animal", "Flora", "Mineral"}:
            family_kind = "Fauna" if discovery_type == "Animal" else discovery_type
            archetype_label = f"{family_kind} family {family_reference}"
            archetype_source = "vp1_family_signal"
        else:
            archetype_source = "category_fallback"

    if family_id:
        wonder_family_label = f"{family_label(family_id)} family"
        wonder_family_source = identity_source
    elif family_reference:
        family_kind = "Fauna" if discovery_type == "Animal" else discovery_type
        wonder_family_label = f"{family_kind} family {family_reference}"
        wonder_family_source = "vp1_family_signal"
    else:
        wonder_family_label = ""
        wonder_family_source = ""

    complete_projector_fingerprint = bool(
        str(getattr(discovery, "message_id", "") or "").strip()
        and str(getattr(discovery, "ua", "") or "").strip()
        and str(getattr(discovery, "vp0", "") or "").strip()
        and str(getattr(discovery, "vp1", "") or "").strip()
    )

    metadata: dict[str, Any] = {
        "archetype_key": archetype_key,
        "archetype_label": archetype_label,
        "archetype_source": archetype_source,
        "fauna_family_id": family_id,
        "fauna_family_label": family_label(family_id),
        "fauna_behavior": behavior,
        "fauna_identity_source": identity_source,
        "fauna_identity_label": identity_label,
        "fauna_family_evidence_count": evidence_count,
        "identity_model_version": IDENTITY_MODEL_VERSION,
        "wonder_family_reference": family_reference,
        "wonder_family_label": wonder_family_label,
        "wonder_family_source": wonder_family_source,
        "wonder_individual_reference": individual_reference,
        "wonder_individual_name": captured_name,
        "wonder_individual_name_status": "captured" if captured_name else "encoded_not_decoded",
        "wonder_individual_signal_label": (
            f"Captured in-game name: {captured_name}"
            if captured_name
            else "Individual name and within-family variation are encoded by VP0"
        ),
        "wonder_projector_fingerprint_status": (
            "complete" if complete_projector_fingerprint else "partial"
        ),
        "wonder_projector_fingerprint_label": (
            "Complete projector fingerprint — exact cross-account reproduction supported"
            if complete_projector_fingerprint
            else "Partial projector identity"
        ),
    }
    metadata.update(descriptor_profile(family_id, pet_match if identity_source == "exact_pet_match" else None))
    return metadata
