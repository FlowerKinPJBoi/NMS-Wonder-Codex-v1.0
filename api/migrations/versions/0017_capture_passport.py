"""Passport-approved Capture Companion sessions.

Revision ID: 0017_capture_passport
Revises: 0016_pegasus_dispatches
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_capture_passport"
down_revision = "0016_pegasus_dispatches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "capture_app_connections",
        sa.Column("device_hash", sa.String(64), primary_key=True),
        sa.Column("user_code_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE")),
        sa.Column("last_poll_at", sa.DateTime(timezone=True)),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True)),
    )
    for name in ("approval_expires_at", "token_expires_at"):
        op.create_index(f"ix_capture_app_connections_{name}", "capture_app_connections", [name])
    op.create_table(
        "capture_auth_rate_windows",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("window", sa.Integer(), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.add_column("capture_submissions", sa.Column("contributor_profile_id", sa.String(36)))
    op.create_foreign_key("fk_capture_contributor_profile", "capture_submissions", "user_profiles",
                          ["contributor_profile_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_capture_submissions_contributor_profile_id", "capture_submissions", ["contributor_profile_id"])


def downgrade():
    op.drop_index("ix_capture_submissions_contributor_profile_id", table_name="capture_submissions")
    op.drop_constraint("fk_capture_contributor_profile", "capture_submissions", type_="foreignkey")
    op.drop_column("capture_submissions", "contributor_profile_id")
    op.drop_table("capture_auth_rate_windows")
    op.drop_table("capture_app_connections")
