from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    website: str = ""  # honeypot

    @field_validator("contributor", "saveName")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return " ".join(value.strip().split())


class ReviewAction(BaseModel):
    note: str = Field(default="", max_length=4000)
    actor: str = Field(default="PJ", max_length=120)


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
