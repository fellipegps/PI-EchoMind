"""Confirmação de encaminhamento das perguntas públicas, sem novos privilégios.

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interactions", sa.Column("unanswered_token_hash", sa.String(64), nullable=True))
    op.add_column("interactions", sa.Column("unanswered_submitted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_interactions_unanswered_token_hash", "interactions", ["unanswered_token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_interactions_unanswered_token_hash", table_name="interactions")
    op.drop_column("interactions", "unanswered_submitted_at")
    op.drop_column("interactions", "unanswered_token_hash")
