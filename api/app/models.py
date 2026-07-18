from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


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
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


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
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AssetSpecimen(Base):
    """A normalized procedural asset, independent of where it was acquired."""

    __tablename__ = "asset_specimens"
    __table_args__ = (UniqueConstraint("asset_key", name="uq_asset_specimen_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    asset_key: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    save_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_role: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False, index=True)
    source_collection: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    source_ordinal: Mapped[int | None] = mapped_column(Integer)
    identity_basis: Mapped[str] = mapped_column(String(120), default="normalized_asset_key", nullable=False)
    publication_state: Mapped[str] = mapped_column(String(30), default="review", nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(80), default="Beta extracted", nullable=False)
    modified_or_special_signal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    delivery_eligibility: Mapped[str] = mapped_column(String(60), default="research_only", nullable=False)
    delivery_evidence_status: Mapped[str] = mapped_column(String(60), default="not_evaluated", nullable=False)
    image_status: Mapped[str] = mapped_column(String(30), default="needed", nullable=False, index=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    sightings: Mapped[list["AssetSighting"]] = relationship(cascade="all, delete-orphan")


class AssetSighting(Base):
    """A possible or verified acquisition location for an asset specimen."""

    __tablename__ = "asset_sightings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset_specimens.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    galaxy_number: Mapped[int | None] = mapped_column(Integer)
    galaxy_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    portal_glyphs: Mapped[str] = mapped_column(String(12), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(60), default="community_evidence", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    public_attribution: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(120), default="admin", nullable=False)
    batch_id: Mapped[str] = mapped_column(String(36), default="", nullable=False, index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FeedbackResponse(Base):
    """Deliberate questionnaire answers kept separate from anonymous analytics."""

    __tablename__ = "feedback_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    respondent_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    visitor_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    page_area: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    ease_score: Mapped[int] = mapped_column(Integer, nullable=False)
    ui_score: Mapped[int] = mapped_column(Integer, nullable=False)
    usefulness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    task_success: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    most_useful: Mapped[str] = mapped_column(Text, default="", nullable=False)
    improvements: Mapped[str] = mapped_column(Text, default="", nullable=False)
    missing_feature: Mapped[str] = mapped_column(Text, default="", nullable=False)
    price_choice: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    custom_price_cents: Mapped[int | None] = mapped_column(Integer)
    monthly_credits: Mapped[int | None] = mapped_column(Integer)
    credit_uses: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    additional_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AnalyticsEvent(Base):
    """Short-lived, privacy-safe anonymous activity used for visit journeys."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    page_title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    referrer_domain: Mapped[str] = mapped_column(String(255), default="Direct", nullable=False, index=True)
    device_class: Mapped[str] = mapped_column(String(20), default="Desktop", nullable=False, index=True)
    browser_family: Mapped[str] = mapped_column(String(40), default="Other", nullable=False, index=True)
    os_family: Mapped[str] = mapped_column(String(40), default="Other", nullable=False, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AnalyticsDailyMetric(Base):
    """Permanent aggregate totals retained after detailed journeys expire."""

    __tablename__ = "analytics_daily_metrics"
    __table_args__ = (
        UniqueConstraint("day", "metric", "dimension", "value", name="uq_analytics_daily_metric"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
