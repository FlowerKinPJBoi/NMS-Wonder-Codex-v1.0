#!/usr/bin/env python3
"""Build the public Wonder Forge v0.1.16 web asset registry.

The input is the seven-folder return extracted from Wonder Forge Expedition
v0.1.16. Source PNGs remain outside the public repository. This tool verifies
every source hash from the chunk manifests, produces bounded WebP derivatives,
and writes an evidence-labeled public registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


REPRESENTATIVE_LABEL = "Representative family image — not this exact specimen."
COMPONENT_LABEL = "Wonder Forge component preview — not a complete discovery."
CATEGORY_LABELS = {
    "fauna": "Fauna",
    "flora": "Flora",
    "minerals": "Minerals",
    "frigates": "Frigates",
    "multitools": "Multi-tools",
    "starship-parts": "Starship parts",
    "freighter-parts": "Freighter parts",
    "multitool-parts": "Multi-tool parts",
}
FAMILY_PREFIXES = {
    "blobrig-blob": "BLOB",
    "catrig-cat": "CAT",
    "spiderrig-spiderfloat": "FLOATSPIDER",
    "spiderrig-hermitcrab": "HERMITCRAB",
    "striderrig-strider": "STRIDER",
    "trexrig-trex": "TREX",
    "triceratopsrig-triceratops": "TRICERATOPS",
    "special-walking-building": "WALKINGBUILDING",
}
OBVIOUS_FAUNA_FAMILIES = {
    "antelope": "ANTELOPE",
    "antelope-bone": "BONECOW",
    "anteloperobot": "ROBOTANTELOPE",
    "antelopetwolegs": "TWOLEGANTELOPE",
    "blobrig-blob": "BLOB",
    "cow": "COW",
    "largebutterfly": "LARGEBUTTERFLY",
    "sixleggedcow": "SIXLEGCOW",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "wonder"


def title_words(value: str) -> str:
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    known = {
        "cactuslrg": "Large Cactus",
        "cactusmed": "Medium Cactus",
        "cactussml": "Small Cactus",
        "dracaenacoloured": "Colored Dracaena",
        "dracaena": "Dracaena",
        "fernlargealt": "Large Fern — Alternate",
        "fernlarge": "Large Fern",
        "fernlight": "Luminous Fern",
        "largetree1": "Large Tree",
        "mediumtree1": "Medium Tree",
        "smalltree1": "Small Tree",
        "peacocktree": "Peacock Tree",
        "skinnedtrees": "Skinned Trees",
        "largerock": "Large Rock",
        "mediumrock": "Medium Rock",
        "resourcerocklarge": "Large Resource Rock",
        "resourcerockshard": "Resource Rock Shard",
        "resourcerock": "Resource Rock",
        "holocombat": "Combat Frigate",
        "holodiplomatic": "Diplomatic Frigate",
        "holoindustrial": "Industrial Frigate",
        "holoscience": "Science Frigate",
        "holosupport": "Support Frigate",
        "royalmultitool": "Royal Multi-tool",
        "sentinelmultitoolb": "Sentinel Multi-tool B",
        "sentinelmultitool": "Sentinel Multi-tool",
        "swarmmultitool": "Swarm Multi-tool",
        "switchmultitool": "Switch Multi-tool",
    }
    compact = value.replace(" ", "").lower()
    if compact in known:
        return known[compact]
    return value.title()


def catalog_identity(entry: dict[str, Any]) -> tuple[str, str]:
    raw_name = str(entry["name"])
    if "--" in raw_name:
        prefix, form = raw_name.split("--", 1)
        family = FAMILY_PREFIXES.get(prefix, "")
        return title_words(form), family

    cleaned = re.sub(r"-scene-mbin-[0-9a-f]+$", "", raw_name.lower())
    cleaned = re.sub(r"-[0-9a-f]{10}$", "", cleaned)
    family = ""
    if entry["category"] == "fauna":
        family = OBVIOUS_FAUNA_FAMILIES.get(cleaned, "")
    return title_words(cleaned), family


def component_name(entry: dict[str, Any]) -> str:
    return title_words(str(entry.get("name") or "Component"))


def source_path(manifest_path: Path, entry: dict[str, Any]) -> Path:
    relative = Path(str(entry["imageRelativePath"]).replace("\\", "/"))
    candidate = (manifest_path.parent / relative).resolve()
    root = manifest_path.parent.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Image escapes its bundle: {relative}")
    return candidate


def render_webp(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((720, 720), Image.Resampling.LANCZOS)
        image.save(
            destination,
            "WEBP",
            quality=78,
            method=4,
            exact=True,
        )


def collect_entries(
    return_root: Path,
    pattern: str,
) -> list[tuple[Path, dict[str, Any]]]:
    rows: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in sorted(return_root.glob(pattern)):
        manifest = read_json(manifest_path)
        if manifest.get("imageCount") != len(manifest.get("entries", [])):
            raise ValueError(f"Manifest count mismatch: {manifest_path}")
        rows.extend((manifest_path, entry) for entry in manifest["entries"])
    return rows


def build(return_root: Path, output_root: Path) -> dict[str, Any]:
    catalog_rows = collect_entries(
        return_root,
        "catalog-*/site-image-manifest.json",
    )
    component_rows = collect_entries(
        return_root,
        "forge-*/site-image-manifest.json",
    )
    if len(catalog_rows) != 186 or len(component_rows) != 166:
        raise ValueError(
            "Expected 186 catalog representatives and 166 component previews; "
            f"received {len(catalog_rows)} and {len(component_rows)}."
        )

    public_catalog: list[dict[str, Any]] = []
    public_components: list[dict[str, Any]] = []
    seen_images: set[str] = set()

    for manifest_path, entry in catalog_rows:
        source = source_path(manifest_path, entry)
        source_digest = sha256(source)
        if source_digest.lower() != str(entry["sourceSha256"]).lower():
            raise ValueError(f"Source hash mismatch: {source}")
        identity = f"{entry['id']}-{source_digest[:12]}"
        category = str(entry["category"])
        name, family_id = catalog_identity(entry)
        relative = Path("catalog") / slug(category) / f"{slug(identity)}.webp"
        destination = output_root / relative
        render_webp(source, destination)
        public_path = f"assets/expedition/{relative.as_posix()}"
        if public_path in seen_images:
            raise ValueError(f"Duplicate public image path: {public_path}")
        seen_images.add(public_path)
        public_catalog.append(
            {
                "id": identity,
                "category": category,
                "category_label": CATEGORY_LABELS.get(category, title_words(category)),
                "family_id": family_id,
                "name": name,
                "image_url": public_path,
                "source_job_id": entry["jobId"],
                "source_sha256": source_digest,
                "evidence_class": "approved_representative",
                "public_label": REPRESENTATIVE_LABEL,
                "exact_specimen": False,
                "record_image_status_unchanged": True,
            }
        )

    for manifest_path, entry in component_rows:
        source = source_path(manifest_path, entry)
        source_digest = sha256(source)
        if source_digest.lower() != str(entry["sourceSha256"]).lower():
            raise ValueError(f"Source hash mismatch: {source}")
        identity = f"{entry['id']}-{source_digest[:12]}"
        category = str(entry["category"])
        family = str(entry.get("family") or "unclassified")
        slot = str(entry.get("slot") or "part")
        relative = (
            Path("components")
            / slug(category)
            / slug(family)
            / slug(slot)
            / f"{slug(identity)}.webp"
        )
        destination = output_root / relative
        render_webp(source, destination)
        public_path = f"assets/expedition/{relative.as_posix()}"
        if public_path in seen_images:
            raise ValueError(f"Duplicate public image path: {public_path}")
        seen_images.add(public_path)
        public_components.append(
            {
                "id": identity,
                "category": category,
                "category_label": CATEGORY_LABELS.get(category, title_words(category)),
                "family": family,
                "slot": slot,
                "name": component_name(entry),
                "image_url": public_path,
                "source_job_id": entry["jobId"],
                "source_sha256": source_digest,
                "evidence_class": "forge_component_preview",
                "public_label": COMPONENT_LABEL,
                "exact_specimen": False,
                "complete_discovery": False,
            }
        )

    public_catalog.sort(key=lambda row: (row["category"], row["name"], row["id"]))
    public_components.sort(
        key=lambda row: (
            row["category"],
            row["family"],
            row["slot"],
            row["name"],
            row["id"],
        )
    )
    category_counts = Counter(row["category"] for row in public_catalog)
    component_counts = Counter(row["category"] for row in public_components)
    registry = {
        "schema_version": 1,
        "release": "wonder-forge-expedition-v0.1.16",
        "source": "Wonder Forge Expedition cumulative site export",
        "counts": {
            "catalog_representatives": len(public_catalog),
            "forge_components": len(public_components),
            "compatibility_groups": 102,
            "catalog_by_category": dict(sorted(category_counts.items())),
            "components_by_category": dict(sorted(component_counts.items())),
        },
        "policy": {
            "approved_exact_image_wins": True,
            "representatives_do_not_change_image_status": True,
            "representative_label": REPRESENTATIVE_LABEL,
            "components_are_not_discoveries": True,
            "component_label": COMPONENT_LABEL,
            "preserve_language_required": True,
        },
        "catalog_entries": public_catalog,
        "component_entries": public_components,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "expedition-catalog.json").write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    registry = build(args.return_root.resolve(), args.output_root.resolve())
    print(
        "Built "
        f"{registry['counts']['catalog_representatives']} representatives and "
        f"{registry['counts']['forge_components']} components."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
