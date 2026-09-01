"""Adiciona parents documentais e vinculo opcional nos chunks.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_chunk_parents",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("parent_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunk_parents_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "document_id",
            "parent_index",
            name="uq_document_chunk_parents_document_id_parent_index",
        ),
        sa.CheckConstraint(
            "parent_index >= 0",
            name="ck_document_chunk_parents_parent_index_nonnegative",
        ),
        sa.CheckConstraint(
            "page_start IS NULL OR page_start > 0",
            name="ck_document_chunk_parents_page_start_positive",
        ),
        sa.CheckConstraint(
            "page_end IS NULL OR page_end > 0",
            name="ck_document_chunk_parents_page_end_positive",
        ),
        sa.CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_end >= page_start",
            name="ck_document_chunk_parents_page_range",
        ),
    )
    op.create_index(
        "ix_document_chunk_parents_tenant_id",
        "document_chunk_parents",
        ["tenant_id"],
    )
    op.create_index(
        "ix_document_chunk_parents_document_id",
        "document_chunk_parents",
        ["document_id"],
    )
    op.create_index(
        "ix_document_chunk_parents_tenant_document",
        "document_chunk_parents",
        ["tenant_id", "document_id"],
    )

    op.add_column(
        "document_chunks",
        sa.Column("parent_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_chunks_parent_id_document_chunk_parents",
        "document_chunks",
        "document_chunk_parents",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_chunks_parent_id",
        "document_chunks",
        ["parent_id"],
    )
    op.execute("ALTER TABLE public.document_chunk_parents ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_document_chunks_parent_id", table_name="document_chunks")
    op.drop_constraint(
        "fk_document_chunks_parent_id_document_chunk_parents",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_column("document_chunks", "parent_id")
    op.drop_table("document_chunk_parents")
