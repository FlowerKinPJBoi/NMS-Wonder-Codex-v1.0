"""Add the product feedback and pricing questionnaire.

Revision ID: 0007_feedback_questionnaire
Revises: 0006_private_analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0007_feedback_questionnaire"
down_revision = "0006_private_analytics"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("respondent_name", sa.String(120), server_default="", nullable=False),
        sa.Column("visitor_type", sa.String(40), nullable=False),
        sa.Column("page_area", sa.String(60), nullable=False),
        sa.Column("ease_score", sa.Integer(), nullable=False),
        sa.Column("ui_score", sa.Integer(), nullable=False),
        sa.Column("usefulness_score", sa.Integer(), nullable=False),
        sa.Column("task_success", sa.String(30), nullable=False),
        sa.Column("most_useful", sa.Text(), server_default="", nullable=False),
        sa.Column("improvements", sa.Text(), server_default="", nullable=False),
        sa.Column("missing_feature", sa.Text(), server_default="", nullable=False),
        sa.Column("price_choice", sa.String(20), nullable=False),
        sa.Column("custom_price_cents", sa.Integer(), nullable=True),
        sa.Column("monthly_credits", sa.Integer(), nullable=True),
        sa.Column("credit_uses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("additional_notes", sa.Text(), server_default="", nullable=False),
    )
    op.create_index("ix_feedback_responses_created_at", "feedback_responses", ["created_at"])
    op.create_index("ix_feedback_responses_visitor_type", "feedback_responses", ["visitor_type"])
    op.create_index("ix_feedback_responses_page_area", "feedback_responses", ["page_area"])
    op.create_index("ix_feedback_responses_task_success", "feedback_responses", ["task_success"])
    op.create_index("ix_feedback_responses_price_choice", "feedback_responses", ["price_choice"])


def downgrade():
    op.drop_table("feedback_responses")
