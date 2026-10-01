"""Add multiple saved NMS Passport profiles.

Revision ID: 0018_nms_profiles
Revises: 0017_capture_passport
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0018_nms_profiles"
down_revision = "0017_capture_passport"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nms_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_profile_id", sa.String(36), sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("platform", sa.String(40), server_default="", nullable=False),
        sa.Column("friend_code_encrypted", sa.Text(), server_default="", nullable=False),
        sa.Column("bot_connect_consent", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("friend_code_verified_at", sa.DateTime(timezone=True)),
        sa.Column("native_owner_uid", sa.String(40), server_default="", nullable=False),
        sa.Column("native_owner_verified_at", sa.DateTime(timezone=True)),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.UniqueConstraint("user_profile_id", "label", name="uq_nms_profiles_user_label"),
    )
    for column in ("user_profile_id", "native_owner_uid", "is_default", "active"):
        op.create_index(f"ix_nms_profiles_{column}", "nms_profiles", [column])

    # Preserve every existing Passport's single encrypted friend code as its first saved NMS profile.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        """
        SELECT id, platform, nms_friend_code_encrypted, bot_connect_consent, friend_code_verified_at
        FROM user_profiles
        WHERE nms_friend_code_encrypted <> ''
        """
    )).mappings()
    for row in rows:
        platform = (row["platform"] or "").strip()
        label = {
            "steam": "Steam",
            "xbox": "Xbox / Game Pass",
            "playstation": "PlayStation",
            "switch": "Nintendo Switch",
        }.get(platform, "Primary NMS profile")
        conn.execute(sa.text(
            """
            INSERT INTO nms_profiles
              (id, user_profile_id, label, platform, friend_code_encrypted,
               bot_connect_consent, friend_code_verified_at, native_owner_uid,
               is_default, active)
            VALUES
              (:id, :user_profile_id, :label, :platform, :friend_code_encrypted,
               :bot_connect_consent, :friend_code_verified_at, '', true, true)
            """
        ), {
            "id": str(__import__("uuid").uuid4()),
            "user_profile_id": row["id"],
            "label": label,
            "platform": platform,
            "friend_code_encrypted": row["nms_friend_code_encrypted"],
            "bot_connect_consent": bool(row["bot_connect_consent"]),
            "friend_code_verified_at": row["friend_code_verified_at"],
        })

    op.add_column("pegasus_dispatches", sa.Column("nms_profile_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_pegasus_dispatch_nms_profile",
        "pegasus_dispatches",
        "nms_profiles",
        ["nms_profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_pegasus_dispatches_nms_profile_id", "pegasus_dispatches", ["nms_profile_id"])


def downgrade():
    op.drop_index("ix_pegasus_dispatches_nms_profile_id", table_name="pegasus_dispatches")
    op.drop_constraint("fk_pegasus_dispatch_nms_profile", "pegasus_dispatches", type_="foreignkey")
    op.drop_column("pegasus_dispatches", "nms_profile_id")
    op.drop_table("nms_profiles")
