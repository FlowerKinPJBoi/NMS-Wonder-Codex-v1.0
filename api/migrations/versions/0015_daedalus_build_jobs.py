"""Add durable Daedalus background build jobs.

Revision ID: 0015_daedalus_build_jobs
Revises: 0014_operational_errors
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_daedalus_build_jobs"
down_revision = "0014_operational_errors"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daedalus_build_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("daedalus_build_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("base_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(30), server_default="preparing", nullable=False),
        sa.Column("phase", sa.String(60), server_default="provider_submission", nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("provider_response_id", sa.String(160), server_default="", nullable=False),
        sa.Column("provider_status", sa.String(40), server_default="preparing", nullable=False),
        sa.Column("retrieval_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reference_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_incident_id", sa.String(36), server_default="", nullable=False),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.UniqueConstraint("session_id", "version", name="uq_daedalus_build_job_version"),
    )
    for column in (
        "actor", "session_id", "status", "phase", "provider_response_id", "error_incident_id",
    ):
        op.create_index(f"ix_daedalus_build_jobs_{column}", "daedalus_build_jobs", [column])


def downgrade():
    op.drop_table("daedalus_build_jobs")
