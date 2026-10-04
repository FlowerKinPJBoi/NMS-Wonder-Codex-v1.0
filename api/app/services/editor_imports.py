"""Small explicit public-data contract; never accept a save tree or an asset blob."""
from __future__ import annotations

import base64
import hashlib
import re
import struct
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .hashing import canonical_hash

SCHEMA = "wonder-codex-editor-import/1"
MAX_RECORDS = 10_000
MAX_REQUEST_BYTES = 10_000_000
DISCOVERY_TYPES = ("Animal", "Flora", "Mineral", "Planet", "SolarSystem")
ASSET_TYPES = ("Starship", "Freighter", "Frigate", "Multitool")
Hex64 = Annotated[str, StringConstraints(pattern=r"^0[xX][0-9A-Fa-f]{1,16}$", max_length=18)]
ShortText = Annotated[str, StringConstraints(max_length=120)]
Descriptor = Annotated[str, StringConstraints(pattern=r"^\^?[A-Za-z0-9_-]{1,159}$", max_length=160)]


def hex64(value: str) -> str:
    return f"0x{int(value, 16):016X}"


class DiscoveryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    DT: Literal["Animal", "Flora", "Mineral", "Planet", "SolarSystem"]
    UA: Hex64
    VP: list[Hex64] = Field(max_length=32)
    CustomName: str = Field(default="", max_length=200)
    CreatureID: str = Field(default="", max_length=120, pattern=r"^\^?[A-Za-z0-9_-]*$")
    CreatureType: str = Field(default="", max_length=120)
    Descriptors: list[Descriptor] = Field(default_factory=list, max_length=100)

    @field_validator("UA")
    @classmethod
    def normalize_ua(cls, value: str) -> str:
        if int(value, 16) > 0xFFFFFFFFFFFFFF:
            raise ValueError("UA must fit the game's 56-bit universal address.")
        return hex64(value)

    @field_validator("VP")
    @classmethod
    def normalize_vp(cls, value: list[str]) -> list[str]:
        return [hex64(item) for item in value]

    @field_validator("CustomName", "CreatureType")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not accepted.")
        return value.strip().lstrip("^")

    @field_validator("CreatureID")
    @classmethod
    def normalize_creature_id(cls, value: str) -> str:
        return value.lstrip("^").upper()

    @field_validator("Descriptors")
    @classmethod
    def normalize_descriptors(cls, value: list[str]) -> list[str]:
        return sorted(set(item.lstrip("^").upper() for item in value))

    @model_validator(mode="after")
    def validate_specimen(self):
        minimum = {"Animal": 3, "Flora": 2, "Mineral": 2}.get(self.DT, 0)
        if len(self.VP) < minimum:
            raise ValueError(f"{self.DT} requires at least {minimum} VP values.")
        if self.CreatureID or self.CreatureType or self.Descriptors:
            if self.DT != "Animal" or not self.CreatureID or len(self.VP) < 4:
                raise ValueError("Pet appearance evidence requires an Animal with an exact local pet/discovery join.")
        return self


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assetType: Literal["Starship", "Freighter", "Frigate", "Multitool"]
    resourceFilename: str = Field(default="", max_length=240)
    seed: Hex64 | None = None
    resourceSeed: Hex64 | None = None
    frigateClass: str = Field(default="", max_length=60, pattern=r"^[A-Za-z0-9_ -]*$")
    displayName: str = Field(default="", max_length=200)
    asset_class: Literal["", "C", "B", "A", "S"] = Field(default="", alias="class")
    sourceRole: Literal["current", "owned_slot", "stored_slot", "fleet_member", "squadron_member",
                        "archived", "historical", "template", "unknown"] = "unknown"
    sourceCollection: str = Field(default="", max_length=120, pattern=r"^[A-Za-z0-9_]*$")
    sourceOrdinal: int | None = Field(default=None, ge=0, le=10000)

    @field_validator("seed", "resourceSeed")
    @classmethod
    def normalize_seed(cls, value: str | None) -> str | None:
        if value is not None and int(value, 16) == 0:
            raise ValueError("A nonzero procedural seed is required.")
        return hex64(value) if value is not None else None

    @field_validator("displayName")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError("Control characters are not accepted.")
        return value.strip().lstrip("^")

    @field_validator("resourceFilename")
    @classmethod
    def normalize_resource(cls, value: str) -> str:
        if not value:
            return value
        value = value.upper()
        if not re.fullmatch(r"MODELS/(?:[A-Z0-9_]+/)*[A-Z0-9_]+\.SCENE\.MBIN", value):
            raise ValueError("Only a game-relative MODELS/...SCENE.MBIN resource name is accepted.")
        if "/BIGGS/" in value:
            raise ValueError("Corvette build identity is not supported by procedural asset imports yet.")
        return value

    @model_validator(mode="after")
    def validate_identity(self):
        if self.assetType == "Frigate":
            if self.resourceSeed is None or not self.frigateClass or self.seed is not None or self.resourceFilename:
                raise ValueError("A Frigate requires only resourceSeed and frigateClass identity.")
        elif not self.resourceFilename or self.seed is None or self.resourceSeed is not None or self.frigateClass:
            raise ValueError("This asset requires only resourceFilename and seed identity.")
        return self


class EditorImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_id: Literal["wonder-codex-editor-import/1"] = Field(alias="schema")
    client_version: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9 ._+/-]+$")
    platform: Literal["Steam", "GOG", "Game Pass", "Xbox / Game Pass PC", "Xbox Game Pass", "Xbox/Game Pass", "Unknown"]
    public_attribution: bool = True
    discoveries: list[DiscoveryRecord] = Field(default_factory=list, max_length=MAX_RECORDS)
    assets: list[AssetRecord] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def validate_count(self):
        count = len(self.discoveries) + len(self.assets)
        if not 1 <= count <= MAX_RECORDS:
            raise ValueError(f"Select between 1 and {MAX_RECORDS} total records for one request.")
        return self


def normalized_discovery(record: DiscoveryRecord) -> tuple[dict, str]:
    raw = {"DT": record.DT, "UA": record.UA, "VP": record.VP,
           **{f"VP{i}": record.VP[i] if i < len(record.VP) else "" for i in range(5)},
           "CustomName": record.CustomName, "CreatureID": record.CreatureID,
           "CreatureType": record.CreatureType, "Descriptors": record.Descriptors,
           "Source": "wonder_codex_editor", "EvidenceStatus": "submitted_unverified", "MessageID": ""}
    block = {"Animal": (3, 3, 3), "Flora": (4, 2, 2), "Mineral": (5, 2, 2)}.get(record.DT)
    if block:
        payload = struct.pack("<QII", int(record.UA, 16), block[0], block[1])
        payload += b"".join(struct.pack("<Q", int(value, 16)) for value in record.VP[:block[2]])
        raw["MessageID"] = base64.b64encode(payload).decode("ascii")
    # Match established imports for <=5 VP values; never collapse longer arrays.
    keys = ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"]
    if len(record.VP) > 5:
        raw.update({f"VP{i}": value for i, value in enumerate(record.VP[5:], start=5)})
        keys.extend(f"VP{i}" for i in range(5, len(record.VP)))
    return raw, canonical_hash(raw, keys)


def normalized_asset(record: AssetRecord) -> dict:
    kind = record.assetType.lower()
    parts = [record.resourceSeed, record.frigateClass] if kind == "frigate" else [record.resourceFilename, record.seed]
    canonical = "|".join([kind, *parts])
    digest = hashlib.sha256(canonical.encode()).hexdigest().upper()
    fields = {"resourceFilename": record.resourceFilename, "seed": record.seed or "",
              "resourceSeed": record.resourceSeed or "", "frigateClass": record.frigateClass,
              "class": record.asset_class, "classProvenance": "current_fleet_record" if kind == "frigate" else "current_inventory",
              "nativeClassKnown": False, "appearanceSeedLocationStatus": "not_a_location_claim",
              "source": "wonder_codex_editor", "evidenceStatus": "submitted_unverified"}
    return {"asset_key": f"PGA-{kind.upper()}-{digest[:16]}", "asset_type": record.assetType,
            "display_name": record.displayName, "source_role": record.sourceRole,
            "source_collection": record.sourceCollection, "source_ordinal": record.sourceOrdinal,
            "identity_basis": "resource_seed_and_frigate_class" if kind == "frigate" else "resource_filename_and_seed",
            "publication_state": "review", "confidence": "Submitted editor evidence",
            "modified_or_special_signal": False, "delivery_eligibility": "research_only",
            "delivery_evidence_status": "not_evaluated", "fields": fields}
