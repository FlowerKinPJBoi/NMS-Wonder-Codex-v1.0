"""Add contributor attribution privacy controls.

Revision ID: 0004_private_attribution
Revises: 0003_image_contributions
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_private_attribution"
down_revision = "0003_image_contributions"
branch_labels = None
depends_on = None


def upgrade():
    for table in [
        "submission_batches",
        "discoveries",
        "pet_discovery_matches",
        "location_verifications",
        "image_contributions",
    ]:
        op.add_column(
            table,
            sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
        )


def downgrade():
    for table in [
        "image_contributions",
        "location_verifications",
        "pet_discovery_matches",
        "discoveries",
        "submission_batches",
    ]:
        op.drop_column(table, "public_attribution")
