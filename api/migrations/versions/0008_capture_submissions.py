"""Add private Capture Companion review pairs.

Revision ID: 0008_capture_submissions
Revises: 0007_feedback_questionnaire
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_capture_submissions"
down_revision = "0007_feedback_questionnaire"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "capture_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), server_default="", nullable=False),
        sa.Column("platform", sa.String(40), server_default="", nullable=False),
        sa.Column("client_version", sa.String(80), server_default="", nullable=False),
        sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("discovery_type", sa.String(40), nullable=False),
        sa.Column("ua", sa.String(32), nullable=False),
        sa.Column("vp0", sa.String(32), server_default="", nullable=False),
        sa.Column("vp1", sa.String(32), server_default="", nullable=False),
        sa.Column("vp2", sa.String(32), server_default="", nullable=False),
        sa.Column("vp3", sa.String(32), server_default="", nullable=False),
        sa.Column("vp4", sa.String(32), server_default="", nullable=False),
        sa.Column("message_id", sa.Text(), server_default="", nullable=False),
        sa.Column("creature_id", sa.String(120), server_default="", nullable=False),
        sa.Column("creature_type", sa.String(120), server_default="", nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("discovery_record", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("image_role", sa.String(60), server_default="full_specimen", nullable=False),
        sa.Column("caption", sa.Text(), server_default="", nullable=False),
        sa.Column("permission_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(255), server_default="", nullable=False),
        sa.Column("content_type", sa.String(100), server_default="image/webp", nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("published_discovery_id", sa.Integer(), sa.ForeignKey("discoveries.id", ondelete="SET NULL")),
        sa.Column("submitter_ip_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("user_agent", sa.Text(), server_default="", nullable=False),
    )
    for column in (
        "status", "contributor", "discovery_type", "ua", "vp1", "creature_id",
        "record_hash", "sha256", "published_discovery_id",
    ):
        op.create_index(f"ix_capture_submissions_{column}", "capture_submissions", [column])


def downgrade():
    op.drop_table("capture_submissions")
