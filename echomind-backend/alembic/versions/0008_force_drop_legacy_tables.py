"""Forca remocao de tabelas legadas

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-14
"""

from alembic import op


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.admin_users CASCADE")
    op.execute("DROP TABLE IF EXISTS public.knowledge_documents CASCADE")


def downgrade() -> None:
    pass
