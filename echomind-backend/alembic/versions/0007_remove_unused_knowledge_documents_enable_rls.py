"""Remove knowledge_documents legado e habilita RLS

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-14
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


RLS_TABLES = (
    "events",
    "faqs",
    "config",
    "unanswered_questions",
    "interactions",
    "langchain_pg_collection",
    "langchain_pg_embedding",
    "alembic_version",
)


def _enable_rls_if_exists(table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('public.{table_name}') IS NOT NULL THEN
                EXECUTE 'ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY';
            END IF;
        END $$;
        """
    )


def _disable_rls_if_exists(table_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('public.{table_name}') IS NOT NULL THEN
                EXECUTE 'ALTER TABLE public.{table_name} DISABLE ROW LEVEL SECURITY';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw")
    op.execute("DROP TABLE IF EXISTS knowledge_documents CASCADE")

    for table_name in RLS_TABLES:
        _enable_rls_if_exists(table_name)


def downgrade() -> None:
    for table_name in reversed(RLS_TABLES):
        _disable_rls_if_exists(table_name)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_documents_tenant_id", "knowledge_documents", ["tenant_id"])
    op.create_index("ix_knowledge_source_id", "knowledge_documents", ["source_id"])
    op.execute(
        """
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
