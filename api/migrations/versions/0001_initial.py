"""Initial Wonder Codex review queue and canonical database.

Revision ID: 0001_initial
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are intentionally explicit so production deployments are repeatable.
    op.create_table(
        "submission_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False, server_default=""),
        sa.Column("client_version", sa.String(80), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("submitter_ip_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("reviewer_note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_submission_batches_status", "submission_batches", ["status"])
    op.create_index("ix_submission_batches_contributor", "submission_batches", ["contributor"])
    op.create_index("ix_submission_batches_source_fingerprint", "submission_batches", ["source_fingerprint"])

    op.create_table(
        "submitted_discoveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("submission_batch_id", sa.String(36), sa.ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("discovery_type", sa.String(40), nullable=False),
        sa.Column("ua", sa.String(32), nullable=False),
        sa.Column("vp0", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp1", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp2", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp3", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp4", sa.String(32), nullable=False, server_default=""),
        sa.Column("message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner", sa.String(160), nullable=False, server_default=""),
        sa.Column("platform", sa.String(40), nullable=False, server_default=""),
        sa.Column("source_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("record_hash", name="uq_submitted_discovery_hash"),
    )
    op.create_index("ix_submitted_discoveries_batch", "submitted_discoveries", ["submission_batch_id"])
    op.create_index("ix_submitted_discoveries_type", "submitted_discoveries", ["discovery_type"])
    op.create_index("ix_submitted_discoveries_ua", "submitted_discoveries", ["ua"])
    op.create_index("ix_submitted_discoveries_vp1", "submitted_discoveries", ["vp1"])
    op.create_index("ix_submitted_discoveries_review", "submitted_discoveries", ["review_status"])

    op.create_table(
        "submitted_pet_matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("submission_batch_id", sa.String(36), sa.ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("creature_id", sa.String(120), nullable=False),
        sa.Column("creature_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("ua", sa.String(32), nullable=False),
        sa.Column("vp0", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp1", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp2", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp3", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp4", sa.String(32), nullable=False, server_default=""),
        sa.Column("secondary_seed", sa.String(32), nullable=False, server_default=""),
        sa.Column("secondary_check", sa.String(40), nullable=False, server_default=""),
        sa.Column("message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("pet_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("discovery_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("record_hash", name="uq_submitted_pet_match_hash"),
    )
    op.create_index("ix_submitted_pet_matches_batch", "submitted_pet_matches", ["submission_batch_id"])
    op.create_index("ix_submitted_pet_matches_creature", "submitted_pet_matches", ["creature_id"])
    op.create_index("ix_submitted_pet_matches_ua", "submitted_pet_matches", ["ua"])
    op.create_index("ix_submitted_pet_matches_vp1", "submitted_pet_matches", ["vp1"])
    op.create_index("ix_submitted_pet_matches_review", "submitted_pet_matches", ["review_status"])

    op.create_table(
        "submission_issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("submission_batch_id", sa.String(36), sa.ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False, server_default=""),
        sa.Column("record_type", sa.String(50), nullable=False, server_default=""),
        sa.Column("creature_id", sa.String(120), nullable=False, server_default=""),
        sa.Column("ua", sa.String(32), nullable=False, server_default=""),
        sa.Column("issue", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_submission_issues_batch", "submission_issues", ["submission_batch_id"])

    op.create_table(
        "discoveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_from_batch_id", sa.String(36), nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("discovery_type", sa.String(40), nullable=False),
        sa.Column("ua", sa.String(32), nullable=False),
        sa.Column("vp0", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp1", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp2", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp3", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp4", sa.String(32), nullable=False, server_default=""),
        sa.Column("message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner", sa.String(160), nullable=False, server_default=""),
        sa.Column("platform", sa.String(40), nullable=False, server_default=""),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("record_hash", name="uq_discovery_hash"),
    )
    op.create_index("ix_discoveries_batch", "discoveries", ["approved_from_batch_id"])
    op.create_index("ix_discoveries_contributor", "discoveries", ["contributor"])
    op.create_index("ix_discoveries_type", "discoveries", ["discovery_type"])
    op.create_index("ix_discoveries_ua", "discoveries", ["ua"])
    op.create_index("ix_discoveries_vp1", "discoveries", ["vp1"])

    op.create_table(
        "pet_discovery_matches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("approved_from_batch_id", sa.String(36), nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), nullable=False),
        sa.Column("creature_id", sa.String(120), nullable=False),
        sa.Column("creature_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("ua", sa.String(32), nullable=False),
        sa.Column("vp0", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp1", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp2", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp3", sa.String(32), nullable=False, server_default=""),
        sa.Column("vp4", sa.String(32), nullable=False, server_default=""),
        sa.Column("secondary_seed", sa.String(32), nullable=False, server_default=""),
        sa.Column("secondary_check", sa.String(40), nullable=False, server_default=""),
        sa.Column("message_id", sa.Text(), nullable=False, server_default=""),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("raw_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("record_hash", name="uq_pet_match_hash"),
    )
    op.create_index("ix_pet_matches_batch", "pet_discovery_matches", ["approved_from_batch_id"])
    op.create_index("ix_pet_matches_contributor", "pet_discovery_matches", ["contributor"])
    op.create_index("ix_pet_matches_creature", "pet_discovery_matches", ["creature_id"])
    op.create_index("ix_pet_matches_ua", "pet_discovery_matches", ["ua"])
    op.create_index("ix_pet_matches_vp1", "pet_discovery_matches", ["vp1"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False, server_default="admin"),
        sa.Column("batch_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_audit_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_batch", "audit_events", ["batch_id"])


def downgrade() -> None:
    for table in [
        "audit_events",
        "pet_discovery_matches",
        "discoveries",
        "submission_issues",
        "submitted_pet_matches",
        "submitted_discoveries",
        "submission_batches",
    ]:
        op.drop_table(table)
