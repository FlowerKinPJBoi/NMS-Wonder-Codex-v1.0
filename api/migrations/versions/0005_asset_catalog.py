"""Add the reviewed procedural asset specimen catalog.

Revision ID: 0005_asset_catalog
Revises: 0004_private_attribution
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_asset_catalog"
down_revision = "0004_private_attribution"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_specimens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("asset_key", sa.String(96), nullable=False),
        sa.Column("asset_type", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(200), server_default="", nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("save_name", sa.String(200), server_default="", nullable=False),
        sa.Column("platform", sa.String(40), server_default="", nullable=False),
        sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("source_role", sa.String(40), server_default="unknown", nullable=False),
        sa.Column("source_collection", sa.String(120), server_default="", nullable=False),
        sa.Column("source_ordinal", sa.Integer(), nullable=True),
        sa.Column("identity_basis", sa.String(120), server_default="normalized_asset_key", nullable=False),
        sa.Column("publication_state", sa.String(30), server_default="review", nullable=False),
        sa.Column("confidence", sa.String(80), server_default="Beta extracted", nullable=False),
        sa.Column("modified_or_special_signal", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("delivery_eligibility", sa.String(60), server_default="research_only", nullable=False),
        sa.Column("delivery_evidence_status", sa.String(60), server_default="not_evaluated", nullable=False),
        sa.Column("image_status", sa.String(30), server_default="needed", nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("asset_key", name="uq_asset_specimen_key"),
    )
    for name, columns in [
        ("ix_asset_specimen_key", ["asset_key"]), ("ix_asset_specimen_type", ["asset_type"]),
        ("ix_asset_specimen_contributor", ["contributor"]), ("ix_asset_specimen_source_role", ["source_role"]),
        ("ix_asset_specimen_publication", ["publication_state"]), ("ix_asset_specimen_special", ["modified_or_special_signal"]),
        ("ix_asset_specimen_image_status", ["image_status"]),
    ]:
        op.create_index(name, "asset_specimens", columns)

    op.create_table(
        "asset_sightings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("asset_specimens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("galaxy_number", sa.Integer(), nullable=True),
        sa.Column("galaxy_name", sa.String(120), server_default="", nullable=False),
        sa.Column("portal_glyphs", sa.String(12), server_default="", nullable=False),
        sa.Column("source", sa.String(60), server_default="community_evidence", nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_asset_sighting_asset", "asset_sightings", ["asset_id"])
    op.create_index("ix_asset_sighting_contributor", "asset_sightings", ["contributor"])
    op.create_index("ix_asset_sighting_status", "asset_sightings", ["status"])


def downgrade():
    op.drop_table("asset_sightings")
    op.drop_table("asset_specimens")
