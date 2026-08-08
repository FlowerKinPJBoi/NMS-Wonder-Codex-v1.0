from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import Settings


MAX_PARTS = 3000
MAX_CORVETTE_MEMBER_BYTES = 40 * 1024 * 1024
MAX_CORVETTE_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
SUPPORTED_FORMATS = {"nmsbase", "nmsprefab", "nmsship", "json"}
SEAT_IDS = {
    "^BUILDCHAIR", "^BUILDCHAIR2", "^BUILDCHAIR3", "^BUILDCHAIR4",
    "^BUILDSOFA", "^BUILDSOFA2", "^BUILDSOFA2L", "^S_BARSTOOL0", "^S_CHAIR0",
}
NORMAL_SCALE_IDS = SEAT_IDS | {
    "^B_RAMP", "^C_RAMP", "^F_RAMP", "^M_RAMP", "^S_RAMP", "^T_RAMP_Q_TOP",
}
CURATED_PARTS: dict[str, dict[str, Any]] = {
    "^C_WALL": {"label": "concrete wall backdrop", "category": "structure", "scale": 1.0},
    "^C_FLOOR": {"label": "concrete floor", "category": "structure", "scale": 1.0},
    "^C_DOOR": {"label": "concrete doorway", "category": "structure", "scale": 1.0},
    "^C_ROOF": {"label": "concrete roof", "category": "structure", "scale": 1.0},
    "^C_RAMP": {"label": "concrete ramp", "category": "structure", "scale": 1.0},
    "^F_FLOOR": {"label": "construction floor", "category": "structure", "scale": 1.0},
    "^F_WALL": {"label": "construction wall", "category": "structure", "scale": 1.0},
    "^F_DOOR": {"label": "construction doorway", "category": "structure", "scale": 1.0},
    "^F_ROOF_M": {"label": "construction roof", "category": "structure", "scale": 1.0},
    "^F_RAMP": {"label": "construction ramp", "category": "structure", "scale": 1.0},
    "^S_FLOOR": {"label": "stone floor", "category": "structure", "scale": 1.0},
    "^S_WALL": {"label": "stone wall", "category": "structure", "scale": 1.0},
    "^S_DOOR": {"label": "stone doorway", "category": "structure", "scale": 1.0},
    "^S_ROOF_M": {"label": "stone roof", "category": "structure", "scale": 1.0},
    "^S_RAMP": {"label": "stone ramp", "category": "structure", "scale": 1.0},
    "^M_FLOOR": {"label": "alloy floor", "category": "structure", "scale": 1.0},
    "^M_WALL": {"label": "alloy wall", "category": "structure", "scale": 1.0},
    "^M_DOOR": {"label": "alloy doorway", "category": "structure", "scale": 1.0},
    "^M_ROOF_M": {"label": "alloy roof", "category": "structure", "scale": 1.0},
    "^M_RAMP": {"label": "alloy ramp", "category": "structure", "scale": 1.0},
    "^B_FLOOR": {"label": "basic floor", "category": "structure", "scale": 1.0},
    "^B_WALL": {"label": "basic wall", "category": "structure", "scale": 1.0},
    "^B_DOOR": {"label": "basic doorway", "category": "structure", "scale": 1.0},
    "^B_ROOF_M": {"label": "basic roof", "category": "structure", "scale": 1.0},
    "^B_RAMP": {"label": "basic ramp", "category": "structure", "scale": 1.0},
    "^BUILDFLATPANEL": {"label": "colorable flat panel", "category": "sign", "scale": 1.0},
    "^BUILDCHAIR4": {"label": "chair", "category": "seat", "scale": 1.0},
    "^BUILDSOFA2": {"label": "sofa", "category": "seat", "scale": 1.0},
    "^BUILDSOFA2L": {"label": "long sofa", "category": "seat", "scale": 1.0},
    "^S_BARSTOOL0": {"label": "bar stool", "category": "seat", "scale": 1.0},
    "^BUILDTABLE": {"label": "table", "category": "surface", "scale": 1.0},
    "^BUILDTABLE2": {"label": "round table", "category": "surface", "scale": 1.0},
    "^BUILDTABLE3": {"label": "small table", "category": "surface", "scale": 1.0},
    "^BUILDWORKTOP": {"label": "worktop", "category": "surface", "scale": 1.0},
    "^MONITORDESK": {"label": "monitor desk", "category": "surface", "scale": 1.0},
    "^DRESSING_TABLE": {"label": "dressing table", "category": "surface", "scale": 1.0},
    "^GAMETABLE": {"label": "game table", "category": "surface", "scale": 1.0},
    "^PLANTER_S": {"label": "small planter", "category": "plant", "scale": 1.0},
    "^PLANTPOT4": {"label": "potted plant", "category": "plant", "scale": 1.0},
    "^SMALLLIGHT": {"label": "small light", "category": "light", "scale": 1.0},
    "^S_TABLELAMP0": {"label": "table lamp", "category": "light", "scale": 1.0},
    "^S_GLOWGLOBE": {"label": "glowing globe", "category": "light", "scale": 1.0},
    "^S_LIGHTSTRIP0": {"label": "white tube light", "category": "light", "scale": 1.0},
    "^WALLLIGHTWHITE": {"label": "white wall light", "category": "sign light", "scale": 1.0},
    "^WALLLIGHTYELLOW": {"label": "yellow wall light", "category": "sign light", "scale": 1.0},
    "^WALLLIGHTRED": {"label": "red wall light", "category": "light", "scale": 1.0},
    "^WALLLIGHTGREEN": {"label": "green wall light", "category": "sign light", "scale": 1.0},
    "^WALLLIGHTBLUE": {"label": "blue wall light", "category": "light", "scale": 1.0},
    "^WALLLIGHTPINK": {"label": "pink wall light", "category": "sign light", "scale": 1.0},
    "^CEILINGLIGHT": {"label": "ceiling light", "category": "light", "scale": 1.0},
    "^BASE_AQUARIUM": {"label": "aquarium", "category": "decoration", "scale": 1.0},
    "^BLD_MINI_BIOFRI": {"label": "mini bio-frigate", "category": "decoration", "scale": 1.0},
    "^BLD_PLANET_HOLO": {"label": "planet hologram", "category": "decoration", "scale": 1.0},
    "^HOLO_DISCO_0": {"label": "holographic display", "category": "decoration", "scale": 1.0},
    "^FRE_ROOM_SCAN": {"label": "planetary probe; giant freighter part", "category": "decoration", "scale": 0.1},
}

SIGN_FONT_3X5 = {
    "A": "010/101/111/101/101", "B": "110/101/110/101/110", "C": "011/100/100/100/011",
    "D": "110/101/101/101/110", "E": "111/100/110/100/111", "F": "111/100/110/100/100",
    "G": "011/100/101/101/011", "H": "101/101/111/101/101", "I": "111/010/010/010/111",
    "J": "001/001/001/101/010", "K": "101/101/110/101/101", "L": "100/100/100/100/111",
    "M": "101/111/111/101/101", "N": "101/111/111/111/101", "O": "010/101/101/101/010",
    "P": "110/101/110/100/100", "Q": "010/101/101/111/011", "R": "110/101/110/101/101",
    "S": "011/100/010/001/110", "T": "111/010/010/010/010", "U": "101/101/101/101/111",
    "V": "101/101/101/101/010", "W": "101/101/111/111/101", "X": "101/101/010/101/101",
    "Y": "101/101/010/010/010", "Z": "111/001/010/100/111",
    "0": "111/101/101/101/111", "1": "010/110/010/010/111", "2": "110/001/010/100/111",
    "3": "110/001/010/001/110", "4": "101/101/111/001/001", "5": "111/100/110/001/110",
    "6": "011/100/111/101/111", "7": "111/001/010/010/010", "8": "111/101/111/101/111",
    "9": "111/101/111/001/110", "!": "010/010/010/000/010", "?": "110/001/010/000/010",
    "-": "000/000/111/000/000", ".": "000/000/000/000/010", " ": "000/000/000/000/000",
}
SIGN_LIGHT_IDS = {
    "white": "^WALLLIGHTWHITE",
    "yellow": "^WALLLIGHTYELLOW",
    "red": "^WALLLIGHTRED",
    "green": "^WALLLIGHTGREEN",
    "blue": "^WALLLIGHTBLUE",
    "pink": "^WALLLIGHTPINK",
}


class BuildOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["add", "move", "remove", "recolor"]
    target_index: int | None
    object_id: str | None
    position: list[float] | None = Field(min_length=3, max_length=3)
    up: list[float] | None = Field(min_length=3, max_length=3)
    forward: list[float] | None = Field(min_length=3, max_length=3)
    scale: float | None
    user_data: int | None = Field(ge=0, le=4_294_967_295)
    visible: bool | None
    rationale: str = Field(min_length=1, max_length=500)


class BuildPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=2000)
    assistant_message: str = Field(min_length=1, max_length=3000)
    operations: list[BuildOperation] = Field(max_length=500)
    warnings: list[str] = Field(max_length=40)


@dataclass
class ParsedBuild:
    raw: bytes
    filename: str
    format: str
    objects: list[dict[str, Any]]
    root: dict[str, Any] | None
    object_key: str
    zip_object_member: str | None
    protected_id: str | None
    validation: dict[str, Any]
    origin: str = "uploaded"
    bootstrap: dict[str, Any] | None = None


@dataclass
class GeneratedBuild:
    body: bytes
    filename: str
    sha256: str
    plan: dict[str, Any]
    validation: dict[str, Any]
    object_count: int
    distinct_object_ids: int
    operation_count: int
    provider_response_id: str


def safe_build_filename(value: str, *, fallback: str = "daedalus-build.nmsbase") -> str:
    name = PurePosixPath((value or "").replace("\\", "/")).name
    if "." in name:
        stem, extension = name.rsplit(".", 1)
        clean_stem = re.sub(r'[^A-Za-z0-9 ._+&-]+', "-", stem).strip(" .-")[:190] or "daedalus-build"
        clean_ext = re.sub(r"[^A-Za-z0-9]+", "", extension).lower()[:20]
        return f"{clean_stem}.{clean_ext}"[:255]
    return fallback


def versioned_filename(source_name: str, version: int) -> str:
    safe = safe_build_filename(source_name)
    if "." in safe:
        stem, extension = safe.rsplit(".", 1)
        return f"{stem}-Daedalus-Pass-{version}.{extension}"[:255]
    return f"{safe}-Daedalus-Pass-{version}.json"[:255]


def _prompt_sign_text(instruction: str) -> str:
    quoted = re.search(r'["“]([^"”]{1,80})["”]', instruction)
    if quoted:
        value = quoted.group(1)
    else:
        described = re.search(r"\b(?:says?|reading|text)\s+(.+?)(?:\s+with\b|$)", instruction, re.IGNORECASE)
        value = described.group(1) if described else ""
    cleaned = " ".join(value.upper().strip(" .").split())[:32]
    return "".join(character if character in SIGN_FONT_3X5 else "?" for character in cleaned)


def _sign_bootstrap(instruction: str, text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lowered = instruction.casefold()
    light_color = next((color for color in SIGN_LIGHT_IDS if re.search(rf"\b{color}\b", lowered)), "white")
    light_id = SIGN_LIGHT_IDS[light_color]
    no_backdrop = bool(re.search(r"\b(?:no|without)\s+(?:a\s+)?backdrop\b", lowered))
    cell = 0.42
    glyph_width = 3
    gap = 1
    total_columns = max(1, len(text) * (glyph_width + gap) - gap)
    text_width = total_columns * cell
    wall_width = 5.333333
    wall_height = 3.333333
    wall_columns = 0 if no_backdrop else max(1, math.ceil((text_width + 1.4) / wall_width))
    timestamp = 1_000_000_000 + int(hashlib.sha256(instruction.encode("utf-8")).hexdigest()[:8], 16) % 1_000_000_000
    records: list[dict[str, Any]] = []

    for column in range(wall_columns):
        x = (column - (wall_columns - 1) / 2) * wall_width
        records.append({
            "Timestamp": timestamp + len(records),
            "ObjectID": "^C_WALL",
            "UserData": 1 if "black" in lowered else 0,
            "Position": [round(x, 6), round(wall_height / 2, 6), 0.0],
            "Up": [0.0, 1.0, 0.0],
            "At": [0.0, 0.0, 1.0],
            "Visible": "true",
        })

    left = -text_width / 2 + cell / 2
    baseline = 0.82
    for glyph_index, character in enumerate(text):
        rows = SIGN_FONT_3X5.get(character, SIGN_FONT_3X5["?"]).split("/")
        for row_index, row in enumerate(rows):
            for column_index, active in enumerate(row):
                if active != "1":
                    continue
                x = left + (glyph_index * (glyph_width + gap) + column_index) * cell
                y = baseline + (4 - row_index) * cell
                records.append({
                    "Timestamp": timestamp + len(records),
                    "ObjectID": light_id,
                    "UserData": 0,
                    "Position": [round(x, 6), round(y, 6), -0.18],
                    "Up": [0.0, 0.0, -1.0],
                    "At": [0.0, 1.0, 0.0],
                    "Visible": "true",
                })
    return records, {
        "origin": "prompt_bootstrap_sign",
        "kind": "sign",
        "text": text,
        "letteringObjectId": light_id,
        "letteringColor": light_color,
        "backdrop": not no_backdrop,
        "partCount": len(records),
        "portablePrefab": True,
    }


def prompt_seed_build(instruction: str) -> tuple[bytes, str, dict[str, Any]]:
    """Create a portable native-prefab canvas when the builder supplies no source file."""
    text = _prompt_sign_text(instruction)
    is_sign = bool(re.search(r"\b(?:sign|marquee|lettering|letters)\b", instruction, re.IGNORECASE))
    if is_sign and text:
        records, bootstrap = _sign_bootstrap(instruction, text)
        stem = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:80] or "Prompt-Sign"
        root = {"Name": f"Daedalus Sign — {text}", "Prefab": records, "Tools": []}
        return json.dumps(root, ensure_ascii=False, indent=2).encode("utf-8"), f"Daedalus-Sign-{stem}.nmsprefab", bootstrap
    bootstrap = {
        "origin": "prompt_blank_prefab",
        "kind": "blank-prefab",
        "partCount": 0,
        "portablePrefab": True,
    }
    root = {"Name": "Daedalus Prompt Build", "Prefab": [], "Tools": []}
    return json.dumps(root, ensure_ascii=False, indent=2).encode("utf-8"), "Daedalus-Prompt-Build.nmsprefab", bootstrap


def _finite_vector(value: Any, *, label: str) -> list[float]:
    if not isinstance(value, list) or len(value) < 3:
        raise HTTPException(status_code=400, detail=f"{label} must contain three numbers.")
    try:
        vector = [float(value[index]) for index in range(3)]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} must contain three numbers.") from exc
    if not all(math.isfinite(number) and abs(number) <= 1_000_000 for number in vector):
        raise HTTPException(status_code=400, detail=f"{label} contains an invalid coordinate.")
    return vector


def _magnitude(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _normalized(vector: list[float], *, label: str) -> list[float]:
    length = _magnitude(vector)
    if length <= 1e-8:
        raise HTTPException(status_code=400, detail=f"{label} cannot be a zero vector.")
    return [value / length for value in vector]


def _scaled(vector: list[float], scale: float, *, label: str) -> list[float]:
    return [round(value * scale, 6) for value in _normalized(vector, label=label)]


def _orientation(up: list[float], forward: list[float], scale: float, *, label: str) -> tuple[list[float], list[float]]:
    normalized_up = _normalized(up, label=f"{label} Up")
    normalized_forward = _normalized(forward, label=f"{label} Forward")
    dot = sum(first * second for first, second in zip(normalized_up, normalized_forward))
    if abs(dot) > 0.02:
        raise HTTPException(status_code=400, detail=f"{label} Up and Forward vectors must be perpendicular.")
    return (
        [round(value * scale, 6) for value in normalized_up],
        [round(value * scale, 6) for value in normalized_forward],
    )


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _find_json_objects(root: dict[str, Any], source_format: str) -> tuple[str, list[dict[str, Any]]]:
    preferred = ("Objects", "Prefab") if source_format != "nmsprefab" else ("Prefab", "Objects")
    for key in preferred:
        value = root.get(key)
        if isinstance(value, list):
            return key, value
    raise HTTPException(status_code=400, detail="The build does not contain an Objects or Prefab array.")


def _validate_objects(objects: list[dict[str, Any]], protected_id: str | None, *, allow_empty: bool = False) -> dict[str, Any]:
    if (not objects and not allow_empty) or len(objects) > MAX_PARTS:
        raise HTTPException(status_code=400, detail="Daedalus builds must contain 1–3,000 placed parts.")
    non_uniform: list[int] = []
    for index, item in enumerate(objects):
        if not isinstance(item, dict) or not str(item.get("ObjectID") or "").startswith("^"):
            raise HTTPException(status_code=400, detail=f"Placed part {index} has an invalid ObjectID.")
        _finite_vector(item.get("Position"), label=f"Placed part {index} Position")
        up = _finite_vector(item.get("Up"), label=f"Placed part {index} Up")
        at = _finite_vector(item.get("At"), label=f"Placed part {index} At")
        up_length, at_length = _magnitude(up), _magnitude(at)
        if up_length <= 0 or at_length <= 0:
            raise HTTPException(status_code=400, detail=f"Placed part {index} has a zero orientation vector.")
        dot = sum(first * second for first, second in zip(up, at)) / (up_length * at_length)
        if abs(dot) > 0.02:
            raise HTTPException(status_code=400, detail=f"Placed part {index} has invalid non-perpendicular orientation vectors.")
        if abs(up_length - at_length) > max(0.005, max(up_length, at_length) * 0.01):
            non_uniform.append(index)
    anchors = [item for item in objects if item.get("ObjectID") == protected_id] if protected_id else []
    if protected_id and len(anchors) != 1:
        raise HTTPException(status_code=400, detail=f"The build must contain exactly one protected {protected_id} record.")
    return {
        "passed": True,
        "objectCount": len(objects),
        "distinctObjectIds": len({item["ObjectID"] for item in objects}),
        "protectedObjectId": protected_id,
        "protectedAnchorCount": len(anchors),
        "uniformScale": not non_uniform,
        "nonUniformSourceIndices": non_uniform[:100],
    }


def parse_build(raw: bytes, filename: str) -> ParsedBuild:
    if not raw:
        raise HTTPException(status_code=400, detail="The build file is empty.")
    safe_name = safe_build_filename(filename)
    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Choose an NMSBASE, nmsprefab, nmsship, or JSON build.")

    if extension == "nmsship":
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = [item for item in archive.infolist() if not item.is_dir()]
                if any(item.flag_bits & 0x1 for item in members):
                    raise HTTPException(status_code=400, detail="Encrypted Corvette packages are not accepted.")
                if any(".." in PurePosixPath(item.filename.replace("\\", "/")).parts for item in members):
                    raise HTTPException(status_code=400, detail="The Corvette package contains an unsafe path.")
                if any(item.file_size > MAX_CORVETTE_MEMBER_BYTES for item in members):
                    raise HTTPException(status_code=413, detail="A Corvette package member exceeds the safe uncompressed limit.")
                if sum(item.file_size for item in members) > MAX_CORVETTE_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=413, detail="The Corvette package exceeds the safe uncompressed limit.")
                object_member = next((item.filename for item in members if PurePosixPath(item.filename).name.casefold() == "objects.json"), None)
                names = Counter(PurePosixPath(item.filename).name.casefold() for item in members)
                if not object_member or any(names[name] != 1 for name in ("objects.json", "so.json", "ccd.json")):
                    raise HTTPException(status_code=400, detail="A Corvette package must contain objects.json, so.json, and ccd.json.")
                objects = json.loads(archive.read(object_member).decode("utf-8-sig"))
        except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail="The Corvette package could not be read.") from exc
        if not isinstance(objects, list):
            raise HTTPException(status_code=400, detail="The Corvette objects.json is not a placed-part array.")
        validation = _validate_objects(objects, "^U_PARAGON")
        return ParsedBuild(raw, safe_name, extension, objects, None, "objects", object_member, "^U_PARAGON", validation)

    try:
        root = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="The build is not valid UTF-8 JSON.") from exc
    if not isinstance(root, dict):
        raise HTTPException(status_code=400, detail="The build root must be a JSON object.")
    object_key, objects = _find_json_objects(root, extension)
    protected_id = "^BASE_FLAG" if extension == "nmsbase" else None
    validation = _validate_objects(objects, protected_id, allow_empty=extension in {"nmsprefab", "json"})
    return ParsedBuild(raw, safe_name, extension, objects, root, object_key, None, protected_id, validation)


def lesson_part_ids(retrieval: dict[str, Any]) -> set[str]:
    output: set[str] = set()
    for item in retrieval.get("items") or []:
        lesson = item.get("lesson") if isinstance(item, dict) else {}
        ground = lesson.get("groundTruth") if isinstance(lesson, dict) else {}
        for part in ground.get("partInventory") or []:
            object_id = str(part.get("objectId") or "") if isinstance(part, dict) else ""
            if object_id.startswith("^"):
                output.add(object_id)
    return output


def candidate_palette(parsed: ParsedBuild, retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    source_counts = Counter(str(item.get("ObjectID") or "") for item in parsed.objects)
    candidates: dict[str, dict[str, Any]] = {}
    for object_id, count in source_counts.items():
        if object_id.startswith("^"):
            candidates[object_id] = {"objectId": object_id, "label": "source part", "category": "existing", "defaultScale": 1.0, "sourceCount": count}
    for object_id in lesson_part_ids(retrieval):
        candidates.setdefault(object_id, {"objectId": object_id, "label": "released lesson part", "category": "learned", "defaultScale": 1.0, "sourceCount": 0})
    if parsed.format != "nmsship":
        for object_id, details in CURATED_PARTS.items():
            candidates[object_id] = {
                "objectId": object_id,
                "label": details["label"],
                "category": details["category"],
                "defaultScale": details["scale"],
                "sourceCount": source_counts.get(object_id, 0),
            }
    return list(candidates.values())[:250]


def _compact_lessons(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    compact = []
    for item in (retrieval.get("items") or [])[:6]:
        lesson = item.get("lesson") or {}
        compact.append({
            "score": item.get("score"),
            "reasons": item.get("reasons") or [],
            "intent": lesson.get("intent") or {},
            "corrections": lesson.get("corrections") or {},
            "groundTruth": lesson.get("groundTruth") or {},
        })
    return compact


def _source_geometry(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "index": index,
        "objectId": item.get("ObjectID"),
        "userData": item.get("UserData"),
        "position": item.get("Position"),
        "up": item.get("Up"),
        "forward": item.get("At"),
    } for index, item in enumerate(objects)]


def _provider_plan(
    parsed: ParsedBuild,
    instruction: str,
    retrieval: dict[str, Any],
    history: list[dict[str, Any]],
    references: list[tuple[str, bytes]],
    settings: Settings,
) -> tuple[BuildPlan, str]:
    if not settings.openai_api_key.strip():
        raise HTTPException(status_code=503, detail="Daedalus generation needs OPENAI_API_KEY in the API service's encrypted environment settings.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="The OpenAI server SDK is not installed in this deployment.") from exc

    palette = candidate_palette(parsed, retrieval)
    context = {
        "request": instruction,
        "format": parsed.format,
        "sourceOrigin": parsed.origin,
        "promptBootstrap": parsed.bootstrap,
        "partLimit": MAX_PARTS,
        "operationLimit": settings.max_daedalus_operations,
        "currentPartCount": len(parsed.objects),
        "protectedObjectId": parsed.protected_id,
        "sourceGeometry": _source_geometry(parsed.objects),
        "allowedPartPalette": palette,
        "releasedCorpusVersion": retrieval.get("corpus_version") or 0,
        "releasedLessons": _compact_lessons(retrieval),
        "priorPasses": history[-6:],
    }
    developer = """You are Daedalus, an expert No Man's Sky base and Corvette architect. Return exactly one submit_build_plan tool call. Treat source indices as immutable identifiers for this pass. Preserve every unmentioned record and all metadata. Never target the protected anchor. Use only Object IDs in allowedPartPalette. Seats and ramps must remain scale 1.0; ^FRE_ROOM_SCAN must be scale 0.1. Use add for new parts, move for existing transforms, recolor for UserData, and remove only when explicitly necessary. Keep doors, stairs, landings, and central walking lanes open. Place furnishings on supported floors. Prefer deliberate groups of seats, tables, lights, plants, and surfaces over scattered objects. When sourceOrigin is prompt_bootstrap_sign, the requested text, fixed-size colored wall lights, and optional backdrop are already constructed: refine that geometry without recreating or duplicating it. When sourceOrigin is prompt_blank_prefab, construct the request on the empty portable prefab canvas. Do not claim that visual collision checks are infallible. Empty operations are allowed when the prompt bootstrap already safely satisfies the request or when no safe edit can satisfy it."""
    content: list[dict[str, Any]] = [{"type": "input_text", "text": json.dumps(context, separators=(",", ":"), ensure_ascii=False)}]
    for mime, body in references:
        content.append({"type": "input_image", "image_url": f"data:{mime};base64,{base64.b64encode(body).decode('ascii')}", "detail": "low"})
    schema = BuildPlan.model_json_schema()
    try:
        client = OpenAI(api_key=settings.openai_api_key, timeout=settings.daedalus_generation_timeout_seconds)
        response = client.responses.create(
            model=settings.daedalus_model,
            reasoning={"effort": settings.daedalus_reasoning_effort},
            store=False,
            parallel_tool_calls=False,
            tool_choice={"type": "function", "name": "submit_build_plan"},
            tools=[{
                "type": "function",
                "name": "submit_build_plan",
                "description": "Submit one bounded, deterministic NMS build-edit plan for server validation and execution.",
                "parameters": schema,
                "strict": True,
            }],
            input=[
                {"role": "developer", "content": developer},
                {"role": "user", "content": content},
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Daedalus's model planner could not complete this pass: {type(exc).__name__}.") from exc
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", "") == "function_call" and getattr(item, "name", "") == "submit_build_plan":
            try:
                return BuildPlan.model_validate_json(item.arguments), str(getattr(response, "id", "") or "")
            except (ValidationError, ValueError, TypeError) as exc:
                raise HTTPException(status_code=502, detail="Daedalus returned a build plan that failed the strict operation schema.") from exc
    raise HTTPException(status_code=502, detail="Daedalus did not return the required build plan.")


def _required_scale(object_id: str, requested: float | None) -> float:
    if object_id in NORMAL_SCALE_IDS:
        return 1.0
    if object_id == "^FRE_ROOM_SCAN":
        return 0.1
    scale = float(requested if requested is not None else CURATED_PARTS.get(object_id, {}).get("scale", 1.0))
    if not math.isfinite(scale) or not 0.05 <= scale <= 4.0:
        raise HTTPException(status_code=400, detail=f"{object_id} requested an unsafe scale.")
    return scale


def _apply_transform(item: dict[str, Any], operation: BuildOperation) -> None:
    object_id = str(item.get("ObjectID") or "")
    if operation.position is not None:
        item["Position"] = [round(value, 6) for value in _finite_vector(operation.position, label="Operation Position")]
    current_up = _finite_vector(item.get("Up"), label="Existing Up")
    current_at = _finite_vector(item.get("At"), label="Existing At")
    current_scale = (_magnitude(current_up) + _magnitude(current_at)) / 2
    scale = _required_scale(object_id, operation.scale if operation.scale is not None else current_scale)
    up = _finite_vector(operation.up, label="Operation Up") if operation.up is not None else current_up
    forward = _finite_vector(operation.forward, label="Operation Forward") if operation.forward is not None else current_at
    item["Up"], item["At"] = _orientation(up, forward, scale, label="Operation")
    if operation.visible is not None:
        item["Visible"] = "true" if operation.visible else "false"


def apply_plan(parsed: ParsedBuild, plan: BuildPlan, retrieval: dict[str, Any], *, maximum_operations: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(plan.operations) > maximum_operations:
        raise HTTPException(status_code=400, detail=f"One Daedalus pass may contain at most {maximum_operations} operations.")
    allowed_ids = {item["objectId"] for item in candidate_palette(parsed, retrieval)}
    source = copy.deepcopy(parsed.objects)
    protected_before = next((copy.deepcopy(item) for item in source if item.get("ObjectID") == parsed.protected_id), None)
    changed: dict[int, dict[str, Any]] = {}
    removed: set[int] = set()
    additions: list[dict[str, Any]] = []
    max_timestamp = max((int(item.get("Timestamp") or 0) for item in source), default=0)

    for operation_number, operation in enumerate(plan.operations, 1):
        if operation.op == "add":
            object_id = str(operation.object_id or "")
            if object_id not in allowed_ids:
                raise HTTPException(status_code=400, detail=f"Operation {operation_number} uses an unapproved ObjectID: {object_id or 'missing'}.")
            if operation.position is None or operation.up is None or operation.forward is None:
                raise HTTPException(status_code=400, detail=f"Operation {operation_number} needs a complete add transform.")
            scale = _required_scale(object_id, operation.scale)
            max_timestamp += 1
            add_up, add_forward = _orientation(
                _finite_vector(operation.up, label="Add Up"),
                _finite_vector(operation.forward, label="Add Forward"),
                scale,
                label="Add",
            )
            additions.append({
                "Timestamp": max_timestamp,
                "ObjectID": object_id,
                "UserData": int(operation.user_data or 0),
                "Position": [round(value, 6) for value in _finite_vector(operation.position, label="Add Position")],
                "Up": add_up,
                "At": add_forward,
                "Visible": "true" if operation.visible is not False else "false",
            })
            continue

        if operation.target_index is None or not 0 <= operation.target_index < len(source):
            raise HTTPException(status_code=400, detail=f"Operation {operation_number} targets an invalid source index.")
        index = operation.target_index
        target = source[index]
        if target.get("ObjectID") == parsed.protected_id:
            raise HTTPException(status_code=400, detail=f"Operation {operation_number} attempted to modify protected {parsed.protected_id}.")
        if operation.op == "remove":
            if index in changed:
                raise HTTPException(status_code=400, detail=f"Operation {operation_number} removes a part already changed in this pass.")
            removed.add(index)
            continue
        if index in removed:
            raise HTTPException(status_code=400, detail=f"Operation {operation_number} changes a part already removed in this pass.")
        item = changed.setdefault(index, copy.deepcopy(target))
        if operation.op == "move":
            _apply_transform(item, operation)
        elif operation.op == "recolor":
            if operation.user_data is None:
                raise HTTPException(status_code=400, detail=f"Operation {operation_number} needs UserData for recoloring.")
            item["UserData"] = int(operation.user_data)

    result = [changed.get(index, item) for index, item in enumerate(source) if index not in removed]
    result.extend(additions)
    if len(result) > MAX_PARTS:
        raise HTTPException(status_code=400, detail=f"This pass would create {len(result):,} parts, exceeding the 3,000-part limit.")
    validation = _validate_objects(result, parsed.protected_id, allow_empty=parsed.format in {"nmsprefab", "json"})
    protected_after = next((item for item in result if item.get("ObjectID") == parsed.protected_id), None)
    if parsed.protected_id and _stable(protected_before) != _stable(protected_after):
        raise HTTPException(status_code=400, detail=f"The generated pass changed protected {parsed.protected_id}.")
    signatures = Counter(_stable({key: item.get(key) for key in ("ObjectID", "UserData", "Position", "Up", "At")}) for item in additions)
    duplicate_additions = sum(count - 1 for count in signatures.values() if count > 1)
    if duplicate_additions:
        raise HTTPException(status_code=400, detail="The generated pass contains duplicate added placements.")
    validation.update({
        "protectedAnchorExact": True,
        "sourceRecordsPreservedUnlessTargeted": True,
        "operationsApplied": len(plan.operations),
        "added": len(additions),
        "removed": len(removed),
        "changed": len(changed),
        "partLimit": MAX_PARTS,
        "requiresBbaOrInGameInspection": True,
    })
    return result, validation


def _write_build(parsed: ParsedBuild, objects: list[dict[str, Any]]) -> bytes:
    if parsed.format == "nmsship":
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(parsed.raw)) as source, zipfile.ZipFile(output, "w") as destination:
            for info in source.infolist():
                body = source.read(info.filename)
                if info.filename == parsed.zip_object_member:
                    body = json.dumps(objects, ensure_ascii=False, indent=2).encode("utf-8")
                destination.writestr(info, body)
        return output.getvalue()
    root = copy.deepcopy(parsed.root or {})
    root[parsed.object_key] = objects
    return json.dumps(root, ensure_ascii=False, indent=2).encode("utf-8")


def generate_build(
    parsed: ParsedBuild,
    instruction: str,
    retrieval: dict[str, Any],
    history: list[dict[str, Any]],
    references: list[tuple[str, bytes]],
    settings: Settings,
    *,
    version: int,
    supplied_plan: BuildPlan | None = None,
) -> GeneratedBuild:
    cleaned_instruction = " ".join(instruction.split())
    if not cleaned_instruction:
        raise HTTPException(status_code=400, detail="Tell Daedalus what to build or change.")
    if len(cleaned_instruction) > 8000:
        raise HTTPException(status_code=400, detail="The Daedalus instruction is too long.")
    if supplied_plan is None:
        plan, response_id = _provider_plan(parsed, cleaned_instruction, retrieval, history, references, settings)
    else:
        plan, response_id = supplied_plan, "test-supplied-plan"
    objects, validation = apply_plan(parsed, plan, retrieval, maximum_operations=settings.max_daedalus_operations)
    if not objects:
        raise HTTPException(status_code=400, detail="Daedalus did not place any parts in this build pass.")
    body = _write_build(parsed, objects)
    reparsed = parse_build(body, versioned_filename(parsed.filename, version))
    if len(reparsed.objects) != len(objects):
        raise HTTPException(status_code=500, detail="The completed build failed its round-trip object count check.")
    if parsed.protected_id:
        before = next(item for item in parsed.objects if item.get("ObjectID") == parsed.protected_id)
        after = next(item for item in reparsed.objects if item.get("ObjectID") == parsed.protected_id)
        if _stable(before) != _stable(after):
            raise HTTPException(status_code=500, detail="The completed build failed its protected-anchor round-trip check.")
    validation.update({
        "roundTripParsed": True,
        "sourceSha256": hashlib.sha256(parsed.raw).hexdigest(),
        "outputSha256": hashlib.sha256(body).hexdigest(),
        "providerPlanSchema": "wonder-codex.daedalus.build-plan.v1",
    })
    plan_record = {
        "schema": "wonder-codex.daedalus.build-plan.v1",
        "status": "APPLIED_AND_VALIDATED",
        "request": cleaned_instruction,
        "summary": plan.summary,
        "assistantMessage": plan.assistant_message,
        "operations": [item.model_dump(mode="json") for item in plan.operations],
        "warnings": plan.warnings,
        "bootstrap": parsed.bootstrap,
        "corpusVersion": int(retrieval.get("corpus_version") or 0),
        "safety": {
            "maximumParts": MAX_PARTS,
            "objectIdsOnly": True,
            "protectedAnchorPreserved": True,
            "uniformScaleRequired": True,
            "preserveUnmentionedGeometry": True,
        },
    }
    return GeneratedBuild(
        body=body,
        filename=versioned_filename(parsed.filename, version),
        sha256=hashlib.sha256(body).hexdigest(),
        plan=plan_record,
        validation=validation,
        object_count=len(objects),
        distinct_object_ids=len({item["ObjectID"] for item in objects}),
        operation_count=len(plan.operations),
        provider_response_id=response_id,
    )
