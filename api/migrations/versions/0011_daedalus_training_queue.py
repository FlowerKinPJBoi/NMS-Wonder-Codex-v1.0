"""Add the guarded Daedalus Builder learning-package queue.

Revision ID: 0011_daedalus_training_queue
Revises: 0010_new_discovery_screenshots
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0011_daedalus_training_queue"
down_revision = "0010_new_discovery_screenshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daedalus_training_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="pending_review", nullable=False),
        sa.Column("contributor", sa.String(120), nullable=False),
        sa.Column("contributor_note", sa.Text(), server_default="", nullable=False),
        sa.Column("reviewer", sa.String(120), server_default="", nullable=False),
        sa.Column("reviewer_note", sa.Text(), server_default="", nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("schema_name", sa.String(120), nullable=False),
        sa.Column("record_id", sa.String(120), nullable=False),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("build_name", sa.String(200), server_default="", nullable=False),
        sa.Column("ground_truth_format", sa.String(30), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("distinct_object_ids", sa.Integer(), nullable=False),
        sa.Column("ground_truth_status", sa.String(40), nullable=False),
        sa.Column("attempt_status", sa.String(40), nullable=False),
        sa.Column("trust_collection", sa.String(100), nullable=False),
        sa.Column("server_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("design_intent", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for column in ("status", "contributor", "sha256", "record_id", "domain"):
        op.create_index(
            f"ix_daedalus_training_submissions_{column}",
            "daedalus_training_submissions",
            [column],
        )


def downgrade():
    op.drop_table("daedalus_training_submissions")
