#!/usr/bin/env python3
"""Build public, ringless Wonder Forge site assets from Expedition bundles.

The source manifests remain evidence artifacts. This builder emits a small,
public-facing catalog with friendly labels and opaque public identifiers.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from zipfile import ZipFile

import numpy as np
from PIL import Image
from scipy.ndimage import (
    binary_dilation,
    distance_transform_edt,
    label,
)


PUBLIC_LABEL = "Representative family image — not this exact specimen."
COMPONENT_LABEL = "Wonder Forge component preview — not a complete discovery."

CATEGORY_LABELS = {
    "fauna": "Fauna",
    "flora": "Flora",
    "frigates": "Frigates",
    "minerals": "Minerals",
    "multitools": "Multi-tools",
    "planets": "Planets",
    "starship-parts": "Starship Parts",
    "freighter-parts": "Freighter Parts",
    "multitool-parts": "Multi-tool Parts",
}

FAMILY_LABELS = {
    "ANTELOPE": "Antelope",
    "ARTHROPOD": "Arthropod",
    "BIRD": "Bird",
    "BLOB": "Blob",
    "CAT": "Cat",
    "COW": "Cow",
    "FLOATSPIDER": "Float Spider",
    "HERMITCRAB": "Hermit Crab",
    "STRIDER": "Strider",
    "TREX": "T-Rex",
    "TRICERATOPS": "Triceratops",
    "WALKINGBUILDING": "Walking Building",
    "BONECOW": "Bone Cow",
    "FLYINGBEETLE": "Flying Beetle",
    "FLYINGLIZARD": "Flying Lizard",
    "GRUNT": "Grunt",
    "LARGEBUTTERFLY": "Large Butterfly",
    "PROTOROLLER": "Proto-Roller",
    "ROBOTANTELOPE": "Robot Antelope",
    "RODENT": "Rodent",
    "SEAHORSE": "Seahorse",
    "SHARK": "Shark",
    "SIXLEGCOW": "Six-Leg Cow",
    "SMALLBIRD": "Small Bird",
    "TWOLEGANTELOPE": "Two-Leg Antelope",
    "WEIRDBUTTERFLY": "Weird Butterfly",
    "ARTHROPODGRUB": "Arthropod Grub",
    "ASTEROIDJELLYFISH": "Asteroid Jellyfish",
    "BUGFIEND": "Bug Fiend",
    "CLAM": "Clam",
    "DEEPSEAFISH": "Deep-Sea Fish",
    "FISHFIEND": "Fish Fiend",
    "FREIGHTERJELLYFISH": "Freighter Jellyfish",
    "GRABBYPLANT": "Grabbing Plant",
    "JELLYBOSSBROOD": "Jellyfish Brood",
    "JELLYBOSS": "Jellyfish Queen",
    "JELLYFISH": "Jellyfish",
    "LANDJELLYFISH": "Land Jellyfish",
    "MYSTERYFISH": "Mystery Fish",
    "SPACEJELLYFISH": "Space Jellyfish",
    "capital-freighter": "Capital Freighter",
    "pirate-freighter": "Pirate Freighter",
    "standard-freighter": "Standard Freighter",
    "bioship": "Living Ship",
    "classic-gold": "Golden Vector",
    "dropship": "Hauler",
    "exotic": "Exotic",
    "fighter": "Fighter",
    "scientific": "Explorer",
    "sentinel": "Sentinel Interceptor",
    "shuttle": "Shuttle",
    "solar": "Solar Ship",
    "switch-fighter": "Switch Fighter",
    "vr-speeder": "VR Speeder",
    "w-racer": "W-Racer",
    "atlasmtparts": "Atlas Multi-tool",
    "atlasmultitool": "Atlas Multi-tool",
}

SLOT_LABELS = {
    "accessories": "Accessories",
    "atlasmtparts": "Atlas Components",
    "ballcontainer": "Spherical Cargo",
    "boxcontainer": "Box Cargo",
    "canopy": "Canopy",
    "cargo": "Cargo",
    "cockpit": "Cockpit",
    "container": "Containers",
    "destructibleparts": "Combat Modules",
    "engine": "Engine",
    "engines": "Engines",
    "fighters": "Body Module",
    "gantry": "Gantry",
    "hull": "Hull",
    "industrial": "Industrial Modules",
    "landinggear": "Landing Gear",
    "nose": "Nose",
    "nosesection": "Nose",
    "parts": "Body Parts",
    "piratefreighterrefs": "Pirate Modules",
    "sailshipparts": "Sail",
    "topwing": "Top Wing",
    "turret": "Turret",
    "weapons": "Weapons",
    "wings": "Wings",
}

CATALOG_NAMES = {
    "clean-wild-blob": "Clean Wild Blob",
    "crested-wolf": "Crested Wolf",
    "classic-cat": "Classic Cat",
    "tusked-hogcat": "Tusked Hog-Cat",
    "classic-wolf": "Classic Wolf",
    "spined-lizard": "Spined Lizard",
    "rare-predator": "Rare Predator",
    "classic-lizard": "Classic Lizard",
    "horned-cat": "Horned Cat",
    "crab-floater": "Crab Floater",
    "jelly-floater": "Jelly Floater",
    "mantis-floater": "Mantis Floater",
    "stalk-eyed-floater": "Stalk-Eyed Floater",
    "mushroom-b12-floater": "Mushroom Floater B12",
    "mushroom-b11-floater": "Mushroom Floater B11",
    "classic-triceratops": "Classic Triceratops",
    "tapir": "Tapir",
    "rhino": "Rhino",
    "diplo": "Diplo",
    "turtle": "Turtle",
    "rhino-rex": "Rhino Rex",
    "rat-rex": "Rat Rex",
    "classic-trex": "Classic T-Rex",
    "croc-rex": "Croc Rex",
    "bird-rex": "Bird Rex",
    "cactuslrg": "Large Cactus",
    "dracaenacoloured": "Colorful Dracaena",
    "dracaena": "Dracaena",
    "fernlargealt": "Broad Giant Fern",
    "fernlarge": "Giant Fern",
    "fernlight": "Luminous Fern",
    "fern": "Fern",
    "floater": "Floating Flora",
    "holocombat": "Combat Frigate",
    "holodiplomatic": "Trade Frigate",
    "holoindustrial": "Industrial Frigate",
    "holoscience": "Exploration Frigate",
    "holosupport": "Support Frigate",
    "base1": "Stone Formation",
    "giantcube": "Giant Cube",
    "giantspike": "Giant Spike",
    "gravelpatchshinynocol": "Natural Gravel Patch",
    "gravelpatchshiny": "Reflective Gravel Patch",
    "pillar1": "Stone Pillar",
    "resourcerocklarge": "Large Resource Rock",
    "resourcerock": "Resource Rock",
    "resourcerockshard": "Resource Shard",
    "squatpillar1": "Squat Stone Pillar",
    "strandbase": "Strand Formation",
    "strands": "Mineral Strands",
    "tinycubes": "Cube Cluster",
    "rodmultitool": "Staff Multi-tool",
    "royalmultitool": "Royal Multi-tool",
    "staffmultitoolatlas": "Atlas Staff",
    "staffmultitoolbone": "Bone Staff",
    "staffmultitoolruin": "Runic Staff",
    "swarmmultitool": "Sentinel Multi-tool",
}

GENERIC_FAUNA = {
    "antelope-bone": ("BONECOW", "Skeletal Grazer"),
    "arthropodgrub": ("ARTHROPODGRUB", "Arthropod Grub"),
    "asteroidjellyfish": ("ASTEROIDJELLYFISH", "Asteroid Jellyfish"),
    "beetle": ("FLYINGBEETLE", "Flying Beetle"),
    "bugfiend": ("BUGFIEND", "Bug Fiend"),
    "clam": ("CLAM", "Armored Clam"),
    "deepseafish": ("DEEPSEAFISH", "Deep-Sea Fish"),
    "fishfiend": ("FISHFIEND", "Predatory Fish"),
    "freighterjellyfish": ("FREIGHTERJELLYFISH", "Freighter Jellyfish"),
    "grabbyplant": ("GRABBYPLANT", "Grabbing Plant"),
    "jellybossbrood": ("JELLYBOSSBROOD", "Jellyfish Brood"),
    "jellyboss": ("JELLYBOSS", "Jellyfish Queen"),
    "jellyfish": ("JELLYFISH", "Jellyfish"),
    "landjellyfish": ("LANDJELLYFISH", "Land Jellyfish"),
    "largebutterfly": ("LARGEBUTTERFLY", "Large Butterfly"),
    "mysteryfish": ("MYSTERYFISH", "Mystery Fish"),
    "spacejellyfish": ("SPACEJELLYFISH", "Space Jellyfish"),
}

COMPOUND_WORDS = (
    "DESTRUCTIBLE", "FREIGHTER", "CONTAINER", "ACCESSORY", "LANDING", "GENERATOR",
    "CYLINDER", "THRUSTER", "COCKPIT", "GANTRY", "ENGINE", "SUBWINGS", "SUBWING",
    "SHIELD", "SUPPORT", "CANNON", "TURRET", "BRIDGE", "CANOPY", "CARGO", "PIRATE",
    "HULL", "WINGS", "WING", "FLAME", "BOTTOM", "FRONT", "DOUBLE", "SINGLE",
    "LARGE", "SMALL", "PANEL", "SPOTLIGHT", "HEADLAMP", "SPHERE", "JOINT",
    "START", "RAIL", "DISC", "CORE", "POD", "BOX", "BALL", "FUEL", "ROD",
    "SAIL", "SHIP", "GUN", "LEFT", "RIGHT", "TOP", "SIDE", "NOSE", "NECK",
    "BACK", "HIGH", "LOW", "CAP", "BASE", "LEG",
)


def slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "form"


def split_compound(token: str) -> list[str]:
    token = token.upper()
    parts: list[str] = []
    while token:
        word = next((word for word in COMPOUND_WORDS if token.startswith(word)), "")
        if word:
            parts.append(word.title())
            token = token[len(word):]
            continue
        match = re.match(r"([A-Z]+?)(?=\d|$)", token)
        if match:
            parts.append(match.group(1).title())
            token = token[len(match.group(1)):]
            continue
        parts.append(token[0])
        token = token[1:]
    return parts


def friendly_component_name(value: str) -> str:
    chunks = re.split(r"[_\-\s]+", value.strip())
    words: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        match = re.fullmatch(r"([A-Za-z]+)(\d*)", chunk)
        if not match:
            words.append(chunk.title())
            continue
        words.extend(split_compound(match.group(1)))
        if match.group(2):
            words.append(match.group(2))
    return " ".join(words).replace("Mt ", "Multi-tool ").strip()


def canonical_part_family(value: str) -> str:
    cleaned = slug(value)
    if cleaned in {"atlasmtparts", "atlasmultitool-scene-mbin"}:
        return "atlasmultitool"
    return cleaned


def friendly_slot(value: str) -> str:
    cleaned = slug(value)
    if cleaned in SLOT_LABELS:
        return SLOT_LABELS[cleaned]
    match = re.fullmatch(r"subwings?-?([a-z])", cleaned)
    if match:
        return f"Sub-wings {match.group(1).upper()}"
    return friendly_component_name(value)


def family_label(value: str) -> str:
    return FAMILY_LABELS.get(value, FAMILY_LABELS.get(slug(value), friendly_component_name(value)))


def catalog_identity(row: dict[str, Any], sequence: int) -> tuple[str, str, str]:
    name = row["name"]
    job = row["jobId"]
    category = row["category"]
    base = name.split("--", 1)[-1]
    base = re.sub(r"-scene-mbin-[0-9a-f]+$", "", base)

    if category == "fauna":
        if name.startswith("blobrig-"):
            family = "BLOB"
        elif name.startswith("catrig-"):
            family = "CAT"
        elif name.startswith("spiderrig-spiderfloat"):
            family = "FLOATSPIDER"
        elif name.startswith("spiderrig-hermitcrab"):
            family = "HERMITCRAB"
        elif name.startswith("striderrig-"):
            family = "STRIDER"
        elif name.startswith("trexrig-"):
            family = "TREX"
        elif name.startswith("triceratopsrig-"):
            family = "TRICERATOPS"
        elif name.startswith("special-walking-building"):
            family = "WALKINGBUILDING"
        else:
            key = re.sub(r"^generic-fauna-", "", job)
            key = re.sub(r"-scene-mbin-[0-9a-f]+$", "", key)
            family, display = GENERIC_FAUNA.get(key, (slug(key).upper().replace("-", "_"), friendly_component_name(key)))
            return family, FAMILY_LABELS.get(family, display), display

        if family == "STRIDER":
            display = f"Strider Form {sequence:02d}"
        elif re.match(r"trex-variant-\d+", base):
            number = int(re.search(r"\d+", base).group())
            display = f"T-Rex Variant {number:02d}"
        elif re.match(r"strider-(?:compatibility|completion)-\d+", base):
            display = f"Strider Form {sequence:02d}"
        elif re.match(r"shell-\d+", base):
            display = f"Hermit Shell {int(re.search(r'\d+', base).group())}"
        elif re.match(r"building-\d+", base):
            suffix = base.removeprefix("building-").upper()
            display = f"Walking Building {suffix}"
        else:
            display = CATALOG_NAMES.get(base, friendly_component_name(base))
        return family, family_label(family), display

    if category == "planets":
        biome = re.sub(r"^planet-|-(?:hologram)$", "", base)
        return biome.upper(), f"{biome.title()} Biome", f"{biome.title()} Biome Globe"

    display = CATALOG_NAMES.get(base, friendly_component_name(base))
    family = slug(base).upper().replace("-", "_")
    return family, display, display


def load_bundles(paths: list[Path], staging: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for bundle in paths:
        with ZipFile(bundle) as archive:
            manifest = json.loads(archive.read("site-image-manifest.json").decode("utf-8-sig"))
            for row in manifest["entries"]:
                relative = PurePosixPath(row["imageRelativePath"].replace("\\", "/"))
                target = staging.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_bytes(archive.read(row["imageRelativePath"]))
                entries.append(dict(row, sourcePath=str(target)))
    return entries


def planet_without_rings(image: np.ndarray) -> np.ndarray:
    rgb = image[:, :, :3].astype(float)
    alpha = image[:, :, 3]
    maximum = rgb.max(axis=2)
    minimum = rgb.min(axis=2)
    saturation = np.divide(
        maximum - minimum,
        maximum,
        out=np.zeros_like(maximum),
        where=maximum > 0,
    )
    colored = (alpha > 10) & (saturation > 0.18) & (maximum > 50)
    components, _ = label(colored)
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    main = components == sizes.argmax()
    ys, xs = np.where(main)
    if not len(xs):
        return image
    x1, x99 = np.percentile(xs, (1, 99))
    y1, y99 = np.percentile(ys, (1, 99))
    cx, cy = (x1 + x99) / 2, (y1 + y99) / 2
    rx, ry = (x99 - x1) / 2 + 12, (y99 - y1) / 2 + 12
    yy, xx = np.indices(alpha.shape)
    keep = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1.03
    output = image.copy()
    output[(alpha > 0) & ~keep] = 0
    return output


def ringless_hologram(image: np.ndarray) -> np.ndarray:
    alpha = image[:, :, 3] > 0
    thickness = distance_transform_edt(alpha)
    core_components, component_count = label(thickness > 12)
    component_sizes = np.bincount(core_components.ravel())
    subject_core = np.zeros_like(alpha)
    for index in range(1, component_count + 1):
        if component_sizes[index] > 35:
            subject_core |= core_components == index

    # The projector rings are deliberately thin, while every usable model has
    # a thicker geometry core. Expanding those cores back through the original
    # alpha retains connected fins, leaves, antennae, and weapon details while
    # excluding the independent circular projector.
    subject = binary_dilation(subject_core, iterations=30) & alpha
    output = image.copy()
    output[alpha & ~subject] = 0
    return output


def save_webp(source: Path, target: Path, *, remove_rings: bool, planet: bool = False) -> None:
    if target.exists():
        return
    image = np.array(Image.open(source).convert("RGBA"))
    if planet:
        image = planet_without_rings(image)
    elif remove_rings:
        image = ringless_hologram(image)
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(target, "WEBP", quality=86, method=6, exact=True)


def build_catalog(rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    public_rows: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    used_paths: Counter[str] = Counter()
    image_jobs: list[tuple[Path, Path, bool, bool]] = []

    for row in sorted(rows, key=lambda item: (item["category"], item["jobId"], item["name"])):
        category = row["category"]
        provisional_family, _, _ = catalog_identity(row, 1)
        family_counts[provisional_family] += 1
        family, family_display, form_name = catalog_identity(row, family_counts[provisional_family])
        stem = slug(f"{family_display}-{form_name}")
        used_paths[f"{category}/{stem}"] += 1
        suffix = used_paths[f"{category}/{stem}"]
        filename = f"{stem}{f'-{suffix:02d}' if suffix > 1 else ''}.webp"
        relative = Path("assets/forge/catalog") / category / filename

        remove_rings = row["jobId"].startswith(("targeted-", "generic-"))
        image_jobs.append((
            Path(row["sourcePath"]),
            output / relative,
            remove_rings,
            category == "planets",
        ))

        if category == "fauna" and family in {
            "ANTELOPE", "ARTHROPOD", "BIRD", "BLOB", "CAT", "COW", "FLOATSPIDER",
            "FLYINGLIZARD", "GRUNT", "HERMITCRAB", "PROTOROLLER", "ROBOTANTELOPE",
            "RODENT", "SEAHORSE", "SHARK", "SIXLEGCOW", "SMALLBIRD", "STRIDER",
            "TREX", "TRICERATOPS", "TWOLEGANTELOPE", "WALKINGBUILDING", "BONECOW",
            "FLYINGBEETLE", "LARGEBUTTERFLY", "WEIRDBUTTERFLY",
        }:
            match_scope = "confirmed_family"
        elif category in {"flora", "minerals"}:
            match_scope = "stable_category_family_signal"
        elif category in {"frigates", "multitools"}:
            match_scope = "stable_asset_type"
        else:
            match_scope = "gallery_only"

        public_rows.append({
            "id": f"representative-{category}-{len(public_rows) + 1:03d}",
            "category_id": category,
            "category_display": CATEGORY_LABELS[category],
            "family_id": family,
            "family_display": family_display,
            "form_name": form_name,
            "image_url": relative.as_posix(),
            "record_eligible": match_scope != "gallery_only",
            "match_scope": match_scope,
            "evidence_class": "approved_representative",
            "exact_specimen": False,
            "display_label": (
                "Wonder Forge biome representative — not this exact planet."
                if category == "planets"
                else PUBLIC_LABEL
            ),
            "ringless": True,
        })

    def build_image(job: tuple[Path, Path, bool, bool]) -> None:
        source, target, remove_rings, planet = job
        save_webp(source, target, remove_rings=remove_rings, planet=planet)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(build_image, image_jobs))

    return {
        "schema_version": 2,
        "release": "wonder-forge-v0.1.18",
        "entry_count": len(public_rows),
        "category_counts": dict(Counter(row["category_id"] for row in public_rows)),
        "record_image_policy": {
            "exact_screenshots_override_representatives": True,
            "representative_label": PUBLIC_LABEL,
            "raw_evidence_unchanged": True,
            "ringless_presentation": True,
        },
        "entries": public_rows,
    }


def build_components(rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    public_rows: list[dict[str, Any]] = []
    variant_counts: Counter[tuple[str, str, str, str]] = Counter()
    image_jobs: list[tuple[Path, Path]] = []

    for row in sorted(rows, key=lambda item: (item["category"], item["family"], item["slot"], item["name"], item["id"])):
        category = row["category"]
        family = canonical_part_family(row["family"])
        slot_id = slug(row["slot"])
        name = friendly_component_name(row["name"])
        key = (category, family, slot_id, name)
        variant_counts[key] += 1
        variant = variant_counts[key]
        display_name = f"{name} · Variant {variant}" if variant > 1 else name
        filename = f"{slug(name)}-{variant:02d}.webp"
        relative = Path("assets/forge/components") / category / family / slot_id / filename
        image_jobs.append((Path(row["sourcePath"]), output / relative))
        public_rows.append({
            "id": f"component-{category}-{len(public_rows) + 1:03d}",
            "category_id": category,
            "category_display": CATEGORY_LABELS[category],
            "family_id": family,
            "family_display": family_label(family),
            "slot_id": slot_id,
            "slot_display": friendly_slot(row["slot"]),
            "component_name": display_name,
            "image_url": relative.as_posix(),
            "exact_specimen": False,
            "complete_discovery": False,
            "display_label": COMPONENT_LABEL,
            "ringless": True,
        })

    def build_image(job: tuple[Path, Path]) -> None:
        source, target = job
        save_webp(source, target, remove_rings=True)

    # Component ring fitting is CPU-heavy but independent per image. Four
    # workers keep the release build practical without the memory spikes seen
    # in the original all-at-once Expedition launcher.
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(build_image, image_jobs))

    return {
        "schema_version": 1,
        "release": "wonder-forge-v0.1.18",
        "entry_count": len(public_rows),
        "category_counts": dict(Counter(row["category_id"] for row in public_rows)),
        "policy": {
            "component_previews_are_not_complete_discoveries": True,
            "ringless_presentation": True,
        },
        "entries": public_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("bundles", nargs="+", type=Path)
    arguments = parser.parse_args()

    arguments.staging.mkdir(parents=True, exist_ok=True)
    rows = load_bundles(arguments.bundles, arguments.staging)
    catalog_rows = [row for row in rows if row["entryType"] == "CATALOG_REPRESENTATIVE"]
    component_rows = [row for row in rows if row["entryType"] == "FORGE_PART_PREVIEW"]
    if len(catalog_rows) != 152 or len(component_rows) != 329:
        raise SystemExit(f"Unexpected return: {len(catalog_rows)} catalog images, {len(component_rows)} components")

    asset_root = arguments.output / "assets/forge"
    asset_root.mkdir(parents=True, exist_ok=True)

    catalog = build_catalog(catalog_rows, arguments.output)
    components = build_components(component_rows, arguments.output)
    (asset_root / "forge-catalog.json").write_text(json.dumps(catalog, indent=2) + "\n")
    (asset_root / "forge-components.json").write_text(json.dumps(components, indent=2) + "\n")
    print(json.dumps({
        "catalog_images": catalog["entry_count"],
        "components": components["entry_count"],
        "catalog_categories": catalog["category_counts"],
        "component_categories": components["category_counts"],
    }, indent=2))


if __name__ == "__main__":
    main()
