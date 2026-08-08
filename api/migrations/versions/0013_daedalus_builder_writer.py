"""Add private, versioned Daedalus build sessions and generated passes.

Revision ID: 0013_daedalus_builder_writer
Revises: 0012_daedalus_corpus
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013_daedalus_builder_writer"
down_revision = "0012_daedalus_corpus"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daedalus_build_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("source_format", sa.String(30), nullable=False),
        sa.Column("source_object_key", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("latest_version", sa.Integer(), server_default="0", nullable=False),
    )
    for column in ("actor", "status", "source_format", "source_sha256"):
        op.create_index(f"ix_daedalus_build_sessions_{column}", "daedalus_build_sessions", [column])

    op.create_table(
        "daedalus_build_passes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("daedalus_build_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("output_filename", sa.String(255), nullable=False),
        sa.Column("output_object_key", sa.Text(), nullable=False),
        sa.Column("output_sha256", sa.String(64), nullable=False),
        sa.Column("output_size_bytes", sa.Integer(), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("distinct_object_ids", sa.Integer(), nullable=False),
        sa.Column("operation_count", sa.Integer(), nullable=False),
        sa.Column("corpus_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("provider_response_id", sa.String(160), server_default="", nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint("session_id", "version", name="uq_daedalus_build_pass_version"),
    )
    op.create_index("ix_daedalus_build_passes_session_id", "daedalus_build_passes", ["session_id"])
    op.create_index("ix_daedalus_build_passes_output_sha256", "daedalus_build_passes", ["output_sha256"])


def downgrade():
    op.drop_table("daedalus_build_passes")
    op.drop_table("daedalus_build_sessions")
