"""Add durable Pegasus Live dispatch queue.

Revision ID: 0016_pegasus_dispatches
Revises: 0015_daedalus_build_jobs
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_pegasus_dispatches"
down_revision = "0015_daedalus_build_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pegasus_dispatches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("requester_profile_id", sa.String(36), sa.ForeignKey("user_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_name", sa.String(120), nullable=False),
        sa.Column("requester_tier", sa.String(30), nullable=False),
        sa.Column("discovery_id", sa.Integer(), sa.ForeignKey("discoveries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("wc_record_id", sa.String(20), nullable=False),
        sa.Column("destination_name", sa.String(200), server_default="", nullable=False),
        sa.Column("galaxy_number", sa.Integer(), nullable=False),
        sa.Column("galaxy_name", sa.String(120), server_default="", nullable=False),
        sa.Column("portal_glyphs", sa.String(12), nullable=False),
        sa.Column("universal_address", sa.String(32), nullable=False),
        sa.Column("status", sa.String(30), server_default="queued", nullable=False),
        sa.Column("phase", sa.String(60), server_default="awaiting_worker", nullable=False),
        sa.Column("status_message", sa.Text(), server_default="", nullable=False),
        sa.Column("worker_id", sa.String(120), server_default="", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    for column in (
        "expires_at",
        "lease_expires_at",
        "requester_profile_id",
        "requester_name",
        "requester_tier",
        "discovery_id",
        "wc_record_id",
        "status",
        "phase",
        "worker_id",
    ):
        op.create_index(f"ix_pegasus_dispatches_{column}", "pegasus_dispatches", [column])


def downgrade():
    op.drop_table("pegasus_dispatches")
