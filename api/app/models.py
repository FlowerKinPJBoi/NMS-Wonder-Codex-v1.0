from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class SubmissionBatch(Base):
    __tablename__ = "submission_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    client_version: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitter_ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    discoveries: Mapped[list["SubmittedDiscovery"]] = relationship(cascade="all, delete-orphan")
    pet_matches: Mapped[list["SubmittedPetMatch"]] = relationship(cascade="all, delete-orphan")
    issues: Mapped[list["SubmissionIssue"]] = relationship(cascade="all, delete-orphan")


class SubmittedDiscovery(Base):
    __tablename__ = "submitted_discoveries"
    __table_args__ = (UniqueConstraint("record_hash", name="uq_submitted_discovery_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    discovery_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ua: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SubmittedPetMatch(Base):
    __tablename__ = "submitted_pet_matches"
    __table_args__ = (UniqueConstraint("record_hash", name="uq_submitted_pet_match_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    creature_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    creature_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ua: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_seed: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_check: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pet_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    discovery_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SubmissionIssue(Base):
    __tablename__ = "submission_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    creature_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ua: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Discovery(Base):
    __tablename__ = "discoveries"
    __table_args__ = (UniqueConstraint("record_hash", name="uq_discovery_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    approved_from_batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    discovery_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    ua: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Catalog curation fields. WC IDs are derived from discovery type + immutable numeric id.
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    galaxy_number: Mapped[int | None] = mapped_column(Integer)
    galaxy_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    portal_glyphs: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    location_status: Mapped[str] = mapped_column(String(30), default="unverified", nullable=False, index=True)
    projector_status: Mapped[str] = mapped_column(String(30), default="data_available", nullable=False, index=True)
    image_status: Mapped[str] = mapped_column(String(30), default="needed", nullable=False, index=True)
    catalog_note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    verifications: Mapped[list["LocationVerification"]] = relationship(cascade="all, delete-orphan")
    images: Mapped[list["ImageContribution"]] = relationship(cascade="all, delete-orphan")


class PetDiscoveryMatch(Base):
    __tablename__ = "pet_discovery_matches"
    __table_args__ = (UniqueConstraint("record_hash", name="uq_pet_match_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    approved_from_batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    creature_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    creature_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ua: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False, index=True)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_seed: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_check: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class LocationVerification(Base):
    __tablename__ = "location_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    discovery_id: Mapped[int] = mapped_column(ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    galaxy_number: Mapped[int | None] = mapped_column(Integer)
    galaxy_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    portal_glyphs: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    reached_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    discovery_present: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    projector_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    submitter_ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ImageContribution(Base):
    __tablename__ = "image_contributions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    discovery_id: Mapped[int] = mapped_column(ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    image_role: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    caption: Mapped[str] = mapped_column(Text, default="", nullable=False)
    permission_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    public_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="image/webp", nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    submitter_ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), default="admin", nullable=False)
    batch_id: Mapped[str] = mapped_column(String(36), default="", nullable=False, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
