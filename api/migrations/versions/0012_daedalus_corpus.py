"""Publish released Daedalus lessons into a versioned retrieval corpus.

Revision ID: 0012_daedalus_corpus
Revises: 0011_daedalus_training_queue
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0012_daedalus_corpus"
down_revision = "0011_daedalus_training_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "daedalus_corpus_state",
        sa.Column("name", sa.String(40), primary_key=True),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "daedalus_corpus_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "submission_id",
            sa.String(36),
            sa.ForeignKey("daedalus_training_submissions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), server_default="active", nullable=False),
        sa.Column("published_version", sa.Integer(), nullable=False),
        sa.Column("last_changed_version", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("recognized_category", sa.String(120), server_default="", nullable=False),
        sa.Column("trust_collection", sa.String(100), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("semantic_text", sa.Text(), server_default="", nullable=False),
        sa.Column("structural_fingerprint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lesson", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disabled_reason", sa.Text(), server_default="", nullable=False),
        sa.UniqueConstraint("submission_id", name="uq_daedalus_corpus_submission"),
    )
    for column in (
        "submission_id",
        "status",
        "published_version",
        "last_changed_version",
        "domain",
        "recognized_category",
        "trust_collection",
        "source_sha256",
    ):
        op.create_index(f"ix_daedalus_corpus_entries_{column}", "daedalus_corpus_entries", [column])
    op.execute("INSERT INTO daedalus_corpus_state (name, version) VALUES ('production', 0)")


def downgrade():
    op.drop_table("daedalus_corpus_entries")
    op.drop_table("daedalus_corpus_state")
