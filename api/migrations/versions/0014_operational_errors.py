"""Add private sanitized operational error incidents.

Revision ID: 0014_operational_errors
Revises: 0013_daedalus_builder_writer
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0014_operational_errors"
down_revision = "0013_daedalus_builder_writer"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "error_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("area", sa.String(40), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), server_default="error", nullable=False),
        sa.Column("actor", sa.String(120), server_default="", nullable=False),
        sa.Column("method", sa.String(10), server_default="", nullable=False),
        sa.Column("path", sa.String(300), server_default="", nullable=False),
        sa.Column("phase", sa.String(60), server_default="request", nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("exception_type", sa.String(160), server_default="", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for column in (
        "occurred_at", "area", "source", "severity", "actor", "path", "phase",
        "status_code", "category", "fingerprint",
    ):
        op.create_index(f"ix_error_incidents_{column}", "error_incidents", [column])


def downgrade():
    op.drop_table("error_incidents")
