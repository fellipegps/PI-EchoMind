"""Adiciona agregados diarios e tenant-scoped de metricas RAG.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_metric_daily",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("chat_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chat_error", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_error", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("retrieved_results", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unanswered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingestion_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingestion_error", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingestion_duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_faq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_event", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_document_chunk", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_document_parent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_other", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint(
            "tenant_id",
            "metric_date",
            name="pk_rag_metric_daily",
        ),
        sa.CheckConstraint(
            "chat_success >= 0 AND chat_error >= 0 "
            "AND retrieval_success >= 0 AND retrieval_error >= 0 "
            "AND retrieved_results >= 0 AND unanswered >= 0 "
            "AND ingestion_success >= 0 AND ingestion_error >= 0 "
            "AND source_faq >= 0 AND source_event >= 0 "
            "AND source_document_chunk >= 0 "
            "AND source_document_parent >= 0 AND source_other >= 0",
            name="ck_rag_metric_daily_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "retrieval_duration_ms >= 0 AND ingestion_duration_ms >= 0",
            name="ck_rag_metric_daily_durations_nonnegative",
        ),
    )
    op.create_index(
        "ix_rag_metric_daily_metric_date",
        "rag_metric_daily",
        ["metric_date"],
    )
    op.execute("ALTER TABLE public.rag_metric_daily ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("rag_metric_daily")
