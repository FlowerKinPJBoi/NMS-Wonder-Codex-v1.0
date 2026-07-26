"""Add console-friendly new discovery screenshot intake.

Revision ID: 0010_new_discovery_screenshots
Revises: 0009_user_accounts
"""
from alembic import op
import sqlalchemy as sa


revision = "0010_new_discovery_screenshots"
down_revision = "0009_user_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "new_discovery_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("discovery_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(200), server_default="", nullable=False),
        sa.Column("platform", sa.String(40), server_default="", nullable=False),
        sa.Column("galaxy_number", sa.Integer(), nullable=True),
        sa.Column("galaxy_name", sa.String(120), server_default="", nullable=False),
        sa.Column("portal_glyphs", sa.String(12), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
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
        sa.Column("published_image_id", sa.String(36), server_default="", nullable=False),
        sa.Column("submitter_ip_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("user_agent", sa.Text(), server_default="", nullable=False),
    )
    for column in ("status", "contributor", "discovery_type", "sha256", "published_discovery_id"):
        op.create_index(f"ix_new_discovery_submissions_{column}", "new_discovery_submissions", [column])


def downgrade():
    op.drop_table("new_discovery_submissions")
