"""Add public catalog curation and location verification workflow.

Revision ID: 0002_catalog_verifications
Revises: 0001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_catalog_verifications"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "discoveries",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("discoveries", sa.Column("display_name", sa.String(200), server_default="", nullable=False))
    op.add_column("discoveries", sa.Column("galaxy_number", sa.Integer(), nullable=True))
    op.add_column("discoveries", sa.Column("galaxy_name", sa.String(120), server_default="", nullable=False))
    op.add_column("discoveries", sa.Column("portal_glyphs", sa.String(12), server_default="", nullable=False))
    op.add_column("discoveries", sa.Column("location_status", sa.String(30), server_default="unverified", nullable=False))
    op.add_column("discoveries", sa.Column("projector_status", sa.String(30), server_default="data_available", nullable=False))
    op.add_column("discoveries", sa.Column("image_status", sa.String(30), server_default="needed", nullable=False))
    op.add_column("discoveries", sa.Column("catalog_note", sa.Text(), server_default="", nullable=False))

    op.create_index("ix_discoveries_location_status", "discoveries", ["location_status"])
    op.create_index("ix_discoveries_projector_status", "discoveries", ["projector_status"])
    op.create_index("ix_discoveries_image_status", "discoveries", ["image_status"])

    op.create_table(
        "location_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "discovery_id",
            sa.Integer(),
            sa.ForeignKey("discoveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("galaxy_number", sa.Integer(), nullable=True),
        sa.Column("galaxy_name", sa.String(120), server_default="", nullable=False),
        sa.Column("portal_glyphs", sa.String(12), server_default="", nullable=False),
        sa.Column("reached_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("discovery_present", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("projector_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(30), server_default="pending", nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("submitter_ip_hash", sa.String(64), server_default="", nullable=False),
        sa.Column("user_agent", sa.Text(), server_default="", nullable=False),
    )
    op.create_index("ix_location_verifications_discovery", "location_verifications", ["discovery_id"])
    op.create_index("ix_location_verifications_contributor", "location_verifications", ["contributor"])
    op.create_index("ix_location_verifications_status", "location_verifications", ["status"])


def downgrade() -> None:
    op.drop_table("location_verifications")
    op.drop_index("ix_discoveries_image_status", table_name="discoveries")
    op.drop_index("ix_discoveries_projector_status", table_name="discoveries")
    op.drop_index("ix_discoveries_location_status", table_name="discoveries")
    for column in [
        "catalog_note",
        "image_status",
        "projector_status",
        "location_status",
        "portal_glyphs",
        "galaxy_name",
        "galaxy_number",
        "display_name",
        "updated_at",
    ]:
        op.drop_column("discoveries", column)
