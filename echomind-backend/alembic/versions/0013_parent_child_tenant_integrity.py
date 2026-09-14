"""Reforca integridade tenant/documento dos vinculos Parent-Child.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-11
"""

from alembic import op


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_id_tenant_id",
        "documents",
        ["id", "tenant_id"],
    )
    op.create_unique_constraint(
        "uq_document_chunk_parents_id_tenant_document",
        "document_chunk_parents",
        ["id", "tenant_id", "document_id"],
    )
    op.create_foreign_key(
        "fk_document_chunk_parents_document_tenant_documents",
        "document_chunk_parents",
        "documents",
        ["document_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_document_chunks_document_tenant_documents",
        "document_chunks",
        "documents",
        ["document_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_document_chunks_parent_tenant_document",
        "document_chunks",
        "document_chunk_parents",
        ["parent_id", "tenant_id", "document_id"],
        ["id", "tenant_id", "document_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_document_chunks_parent_tenant_document",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_document_chunks_document_tenant_documents",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_document_chunk_parents_document_tenant_documents",
        "document_chunk_parents",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_document_chunk_parents_id_tenant_document",
        "document_chunk_parents",
        type_="unique",
    )
    op.drop_constraint(
        "uq_documents_id_tenant_id",
        "documents",
        type_="unique",
    )
