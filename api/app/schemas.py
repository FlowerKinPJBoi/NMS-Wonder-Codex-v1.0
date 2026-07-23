from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SubmissionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = ""
    createdUTC: str = ""
    contributor: str = Field(min_length=1, max_length=120)
    saveName: str = Field(min_length=1, max_length=200)
    platform: str = Field(default="", max_length=40)
    summary: dict[str, Any] = Field(default_factory=dict)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    discoveries: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    publicAttribution: bool = True
    website: str = ""  # honeypot

    @field_validator("contributor", "saveName")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ReviewAction(BaseModel):
    note: str = Field(default="", max_length=4000)
    actor: str = Field(default="PJ", max_length=120)


class VerificationReviewAction(ReviewAction):
    apply_location: bool = True


class SubmissionListItem(BaseModel):
    id: str
    created_at: str
    contributor: str
    save_name: str
    platform: str
    status: str
    discovery_count: int
    pet_match_count: int
    issue_count: int


class LocationVerificationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    discovery_id: int = Field(gt=0)
    contributor: str = Field(min_length=1, max_length=120)
    galaxy_number: int | None = Field(default=None, ge=1, le=256)
    galaxy_name: str = Field(default="", max_length=120)
    portal_glyphs: str = Field(default="", max_length=12)
    reached_system: bool = False
    discovery_present: bool = False
    projector_confirmed: bool = False
    notes: str = Field(default="", max_length=4000)
    public_attribution: bool = True
    website: str = ""  # honeypot

    @field_validator("contributor", "galaxy_name")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("portal_glyphs", mode="before")
    @classmethod
    def clean_glyphs(cls, value: str) -> str:
        cleaned = re.sub(r"[^0-9A-F]", "", value.upper())
        if cleaned and len(cleaned) != 12:
            raise ValueError("Portal glyph code must contain exactly 12 hexadecimal glyph values.")
        return cleaned

    @model_validator(mode="after")
    def require_evidence(self):
        if not any([
            self.portal_glyphs,
            self.galaxy_number,
            self.reached_system,
            self.discovery_present,
            self.projector_confirmed,
            self.notes.strip(),
        ]):
            raise ValueError("Add a location, a verification result, or reviewer notes before submitting.")
        return self


class CatalogUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str = Field(default="admin", max_length=120)
    display_name: str | None = Field(default=None, max_length=200)
    galaxy_number: int | None = Field(default=None, ge=1, le=256)
    galaxy_name: str | None = Field(default=None, max_length=120)
    portal_glyphs: str | None = Field(default=None, max_length=12)
    location_status: str | None = Field(default=None, pattern="^(unverified|pending|verified|disputed)$")
    projector_status: str | None = Field(default=None, pattern="^(data_available|verified|unverified|disputed)$")
    image_status: str | None = Field(default=None, pattern="^(needed|pending|available)$")
    catalog_note: str | None = Field(default=None, max_length=4000)

    @field_validator("display_name", "galaxy_name")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.strip().split())

    @field_validator("portal_glyphs", mode="before")
    @classmethod
    def clean_optional_glyphs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"[^0-9A-F]", "", value.upper())
        if cleaned and len(cleaned) != 12:
            raise ValueError("Portal glyph code must contain exactly 12 hexadecimal glyph values.")
        return cleaned


class ImageReviewAction(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=4000)
    approval_role: Literal["primary", "alternate"] = "alternate"


class AssetManifestImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contributor: str = Field(min_length=1, max_length=120)
    public_attribution: bool = True
    manifest: dict[str, Any]

    @field_validator("contributor")
    @classmethod
    def clean_contributor(cls, value: str) -> str:
        return " ".join(value.strip().split())


class AssetCatalogUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=200)
    source_role: Literal[
        "current", "owned_slot", "stored_slot", "fleet_member", "squadron_member",
        "archived", "historical", "template", "unknown",
    ] | None = None
    source_collection: str | None = Field(default=None, max_length=120)
    source_ordinal: int | None = Field(default=None, ge=0)
    identity_basis: str | None = Field(default=None, max_length=120)
    publication_state: Literal["review", "published", "hidden"] | None = None
    confidence: str | None = Field(default=None, max_length=80)
    modified_or_special_signal: bool | None = None
    delivery_eligibility: str | None = Field(default=None, max_length=60)
    delivery_evidence_status: str | None = Field(default=None, max_length=60)
    image_status: Literal["needed", "pending", "available"] | None = None
    reviewer_note: str | None = Field(default=None, max_length=4000)

    @field_validator(
        "display_name", "source_collection", "identity_basis", "confidence",
        "delivery_eligibility", "delivery_evidence_status", "reviewer_note",
    )
    @classmethod
    def clean_asset_text(cls, value: str | None) -> str | None:
        return " ".join(value.strip().split()) if value is not None else value


class AnalyticsEventPayload(BaseModel):
    """A deliberately small, allowlisted public analytics envelope."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    event_type: Literal[
        "page_view",
        "catalog_filter",
        "map_filter",
        "record_view",
        "asset_view",
        "contribution_started",
        "contribution_completed",
        "import_analyzed",
        "import_submitted",
        "download",
        "transit_ticket_download",
        "projector_decode",
    ]
    path: str = Field(default="/", max_length=500)
    title: str = Field(default="", max_length=200)
    referrer: str = Field(default="", max_length=1000)
    properties: dict[str, Any] = Field(default_factory=dict, max_length=30)
