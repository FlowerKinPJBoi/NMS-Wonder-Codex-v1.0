"""Import-only Editor Passport sessions and atomic replay receipts.

Revision ID: 0019_editor_imports
Revises: 0018_nms_profiles
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019_editor_imports"
down_revision = "0018_nms_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "editor_app_connections",
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
        op.create_index(f"ix_editor_app_connections_{name}", "editor_app_connections", [name])
    op.create_table(
        "editor_import_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("profile_id", "idempotency_key", name="uq_editor_import_request"),
    )


def downgrade():
    op.drop_table("editor_import_receipts")
    op.drop_table("editor_app_connections")
