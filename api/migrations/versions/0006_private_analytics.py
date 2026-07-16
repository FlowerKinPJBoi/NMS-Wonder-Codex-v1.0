"""Add privacy-safe first-party analytics.

Revision ID: 0006_private_analytics
Revises: 0005_asset_catalog
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_private_analytics"
down_revision = "0005_asset_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("session_hash", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("page_title", sa.String(200), server_default="", nullable=False),
        sa.Column("referrer_domain", sa.String(255), server_default="Direct", nullable=False),
        sa.Column("device_class", sa.String(20), server_default="Desktop", nullable=False),
        sa.Column("browser_family", sa.String(40), server_default="Other", nullable=False),
        sa.Column("os_family", sa.String(40), server_default="Other", nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    for name, columns in [
        ("ix_analytics_events_occurred", ["occurred_at"]),
        ("ix_analytics_events_session", ["session_hash"]),
        ("ix_analytics_events_type", ["event_type"]),
        ("ix_analytics_events_path", ["path"]),
        ("ix_analytics_events_referrer", ["referrer_domain"]),
        ("ix_analytics_events_device", ["device_class"]),
        ("ix_analytics_events_browser", ["browser_family"]),
        ("ix_analytics_events_os", ["os_family"]),
    ]:
        op.create_index(name, "analytics_events", columns)

    op.create_table(
        "analytics_daily_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("dimension", sa.String(40), nullable=False),
        sa.Column("value", sa.String(300), nullable=False),
        sa.Column("count", sa.BigInteger(), server_default="0", nullable=False),
        sa.UniqueConstraint("day", "metric", "dimension", "value", name="uq_analytics_daily_metric"),
    )
    for name, columns in [
        ("ix_analytics_daily_day", ["day"]),
        ("ix_analytics_daily_metric", ["metric"]),
        ("ix_analytics_daily_dimension", ["dimension"]),
    ]:
        op.create_index(name, "analytics_daily_metrics", columns)


def downgrade():
    op.drop_table("analytics_daily_metrics")
    op.drop_table("analytics_events")
