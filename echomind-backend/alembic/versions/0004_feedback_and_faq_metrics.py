"""feedback_and_faq_metrics

Revision ID: 0004
Revises: 0003_embedding_dim_384
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("faqs", sa.Column("total_consults", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("faqs", sa.Column("positive_feedback", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("faqs", sa.Column("negative_feedback", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("interactions", sa.Column("feedback_helpful", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("interactions", "feedback_helpful")
    op.drop_column("faqs", "negative_feedback")
    op.drop_column("faqs", "positive_feedback")
    op.drop_column("faqs", "total_consults")
