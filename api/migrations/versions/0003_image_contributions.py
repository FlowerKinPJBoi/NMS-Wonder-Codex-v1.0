"""image contribution queue and published media metadata

Revision ID: 0003_image_contributions
Revises: 0002_catalog_verifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_image_contributions"
down_revision = "0002_catalog_verifications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_contributions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("discovery_id", sa.Integer(), sa.ForeignKey("discoveries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contributor", sa.String(length=120), nullable=False),
        sa.Column("image_role", sa.String(length=60), nullable=False),
        sa.Column("caption", sa.Text(), server_default="", nullable=False),
        sa.Column("permission_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("public_url", sa.Text(), server_default="", nullable=False),
        sa.Column("original_filename", sa.String(length=255), server_default="", nullable=False),
        sa.Column("content_type", sa.String(length=100), server_default="image/webp", nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("submitter_ip_hash", sa.String(length=64), server_default="", nullable=False),
        sa.Column("user_agent", sa.Text(), server_default="", nullable=False),
    )
    op.create_index("ix_image_contributions_discovery_id", "image_contributions", ["discovery_id"])
    op.create_index("ix_image_contributions_status", "image_contributions", ["status"])
    op.create_index("ix_image_contributions_contributor", "image_contributions", ["contributor"])
    op.create_index("ix_image_contributions_image_role", "image_contributions", ["image_role"])
    op.create_index("ix_image_contributions_sha256", "image_contributions", ["sha256"])
    op.create_index("ix_image_contributions_is_primary", "image_contributions", ["is_primary"])


def downgrade():
    op.drop_table("image_contributions")
