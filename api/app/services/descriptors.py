from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


DESCRIPTOR_PROFILE_VERSION = "wonder-codex-descriptor-profile/v0.1"
_TOKEN = re.compile(r"^[A-Z0-9_]{1,100}$")
_FAMILY = re.compile(r"^[A-Z0-9_]{1,120}$")
_LEXICAL_CATEGORIES = (
    ("head", ("HEAD", "FACE", "MOUTH", "EYE", "BEAK")),
    ("horns", ("HORN", "ANTLER", "TUSK")),
    ("tail", ("TAIL",)),
    ("body", ("BODY", "TORSO", "BACK", "SHELL", "ARMOUR", "ARMOR")),
    ("limbs", ("LEG", "ARM", "HAND", "FOOT", "FEET", "WING")),
    ("surface", ("FUR", "HAIR", "SCALE", "SPIKE", "FEATHER")),
    ("accessory", ("ACCESSORY", "ACC", "BACKPACK", "JELLY")),
)


def normalize_descriptor_tokens(values: Iterable[Any] | None) -> list[str]:
    tokens: set[str] = set()
    for value in values or ():
        token = str(value or "").strip().lstrip("^").upper()
        if _TOKEN.fullmatch(token):
            tokens.add(token)
    return sorted(tokens)[:128]


def descriptor_tokens_from_match(match: Any | None) -> list[str]:
    if match is None:
        return []
    # vars() avoids lazy-loading raw_record for the map's deliberately lean query.
    loaded = vars(match)
    if "_sa_instance_state" in loaded and "raw_record" not in loaded:
        return []
    raw_record = loaded.get("raw_record", getattr(match, "raw_record", None))
    if not isinstance(raw_record, dict):
        return []
    values = raw_record.get("Descriptors", raw_record.get("descriptors", []))
    if not isinstance(values, list):
        return []
    return normalize_descriptor_tokens(values)


def descriptor_visual_hints(values: Iterable[Any] | None) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    for token in normalize_descriptor_tokens(values):
        parts = set(token.split("_"))
        for category, terms in _LEXICAL_CATEGORIES:
            if parts.intersection(terms):
                hints.append({
                    "token": token,
                    "category": category,
                    "evidence": "token_name_only",
                })
                break
    return hints


def visual_profile_fingerprint(family: Any, values: Iterable[Any] | None) -> str:
    normalized_family = str(family or "").strip().lstrip("^").upper()
    if not _FAMILY.fullmatch(normalized_family):
        normalized_family = "UNKNOWN"
    canonical = "|".join((normalized_family, *normalize_descriptor_tokens(values)))
    return f"WCV-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24].upper()}"


def descriptor_profile(family: Any, match: Any | None) -> dict[str, Any]:
    tokens = descriptor_tokens_from_match(match)
    hints = descriptor_visual_hints(tokens)
    categories = list(dict.fromkeys(hint["category"] for hint in hints))
    return {
        "descriptor_profile_version": DESCRIPTOR_PROFILE_VERSION,
        "descriptor_tokens": tokens,
        "descriptor_token_count": len(tokens),
        "descriptor_visual_hints": hints,
        "descriptor_visual_categories": categories,
        "visual_profile_fingerprint": visual_profile_fingerprint(family, tokens),
        "descriptor_evidence_status": (
            "observed_save_tokens" if tokens else "no_descriptor_tokens_observed"
        ),
        "descriptor_interpretation_status": (
            "lexical_hints_only" if hints else "awaiting_projector_mapping"
        ),
        "representative_image_policy": "representative_not_exact_without_specimen_image",
        "representative_image_notice": "Representative reconstruction — not the exact specimen.",
    }
