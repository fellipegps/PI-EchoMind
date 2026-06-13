"""Adiciona tenant_id para isolamento multiusuario

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


TABLES = (
    "faqs",
    "events",
    "config",
    "interactions",
    "unanswered_questions",
    "knowledge_documents",
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
        op.drop_column(table, "tenant_id")
