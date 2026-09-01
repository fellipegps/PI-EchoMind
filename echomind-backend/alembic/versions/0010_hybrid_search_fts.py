"""Adiciona índices full-text para a busca híbrida tenant-scoped.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-30
"""

from alembic import op


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índices de expressão: não duplicam o corpus nem introduzem tabela global.
    op.execute(
        "CREATE INDEX ix_faqs_fts_portuguese ON public.faqs USING gin "
        "(to_tsvector('portuguese', coalesce(question, '') || ' ' || coalesce(answer, '')))"
    )
    op.execute(
        "CREATE INDEX ix_events_fts_portuguese ON public.events USING gin "
        "(to_tsvector('portuguese', "
        "coalesce(title, '') || ' ' || coalesce(event_date, '') || ' ' || "
        "coalesce(event_type, '') || ' ' || coalesce(description, '')))"
    )
    op.execute(
        "CREATE INDEX ix_documents_fts_portuguese ON public.documents USING gin "
        "(to_tsvector('portuguese', "
        "coalesce(filename, '') || ' ' || coalesce(document_type, '') || ' ' || "
        "coalesce(document_number, '') || ' ' || coalesce(department, '')))"
    )
    op.execute(
        "CREATE INDEX ix_document_chunks_fts_portuguese ON public.document_chunks USING gin "
        "(to_tsvector('portuguese', coalesce(content, '') || ' ' || coalesce(section_title, '')))"
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_fts_portuguese", table_name="document_chunks")
    op.drop_index("ix_documents_fts_portuguese", table_name="documents")
    op.drop_index("ix_events_fts_portuguese", table_name="events")
    op.drop_index("ix_faqs_fts_portuguese", table_name="faqs")
