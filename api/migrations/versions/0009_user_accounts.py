"""Add managed-auth user profiles and access tiers.

Revision ID: 0009_user_accounts
Revises: 0008_capture_submissions
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_user_accounts"
down_revision = "0008_capture_submissions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("auth_subject", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contributor_name", sa.String(120), nullable=False),
        sa.Column("public_attribution", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("platform", sa.String(40), server_default="", nullable=False),
        sa.Column("access_tier", sa.String(30), server_default="regular", nullable=False),
        sa.Column("account_status", sa.String(30), server_default="active", nullable=False),
        sa.Column("discord_user_id", sa.String(40), nullable=True),
        sa.Column("nms_friend_code_encrypted", sa.Text(), server_default="", nullable=False),
        sa.Column("bot_connect_consent", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("friend_code_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("auth_subject", name="uq_user_profiles_auth_subject"),
        sa.UniqueConstraint("discord_user_id", name="uq_user_profiles_discord_user_id"),
    )
    for column in ("auth_subject", "contributor_name", "access_tier", "account_status"):
        op.create_index(f"ix_user_profiles_{column}", "user_profiles", [column])


def downgrade():
    op.drop_table("user_profiles")
