"""criacao inicial das tabelas echomind

Revision ID: 0001
Revises: 
Create Date: 2025-01-01 00:00:00.000000

Cria todas as tabelas do EchoMind:
  - faqs
  - events
  - config
  - interactions
  - unanswered_questions
  - knowledge_documents (com índice HNSW do pgvector)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
import os

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))


def upgrade() -> None:
    # Habilita a extensão pgvector (idempotente)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── faqs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "faqs",
        sa.Column("id",            sa.String(),  primary_key=True, nullable=False),
        sa.Column("question",      sa.Text(),    nullable=False),
        sa.Column("answer",        sa.Text(),    nullable=False),
        sa.Column("show_on_totem", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at",    sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",    sa.DateTime(), nullable=True),
    )
    op.create_index("ix_faqs_show_on_totem", "faqs", ["show_on_totem"])

    # ── events ────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id",          sa.String(), primary_key=True, nullable=False),
        sa.Column("title",       sa.Text(),   nullable=False),
        sa.Column("event_date",  sa.String(), nullable=False),
        sa.Column("event_type",  sa.String(), nullable=False),
        sa.Column("description", sa.Text(),   nullable=True),
        sa.Column("created_at",  sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",  sa.DateTime(), nullable=True),
    )
    op.create_index("ix_events_event_date", "events", ["event_date"])

    # ── config ────────────────────────────────────────────────────────────────
    op.create_table(
        "config",
        sa.Column("id",                  sa.String(), primary_key=True, nullable=False),
        sa.Column("company_name",        sa.String(), nullable=False, server_default="EchoMind Institution"),
        sa.Column("description",         sa.Text(),   nullable=True),
        sa.Column("tone_of_voice",       sa.String(), nullable=True, server_default="profissional e cordial"),
        sa.Column("totem_voice_gender",  sa.String(), nullable=True, server_default="feminina"),
        sa.Column("website",             sa.String(), nullable=True),
        sa.Column("phone",               sa.String(), nullable=True),
        sa.Column("address",             sa.Text(),   nullable=True),
        sa.Column("business_hours",      sa.String(), nullable=True),
        sa.Column("updated_at",          sa.DateTime(), nullable=True),
    )

    # ── interactions ──────────────────────────────────────────────────────────
    op.create_table(
        "interactions",
        sa.Column("id",           sa.String(),  primary_key=True, nullable=False),
        sa.Column("question",     sa.Text(),    nullable=False),
        sa.Column("answer",       sa.Text(),    nullable=True),
        sa.Column("was_answered", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("asked_at",     sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interactions_asked_at", "interactions", ["asked_at"])
    op.create_index("ix_interactions_was_answered", "interactions", ["was_answered"])

    # ── unanswered_questions ──────────────────────────────────────────────────
    op.create_table(
        "unanswered_questions",
        sa.Column("id",                 sa.String(),  primary_key=True, nullable=False),
        sa.Column("canonical_question", sa.Text(),    nullable=False),
        sa.Column("count",              sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_asked",        sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_asked",         sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("similar_questions",  sa.Text(),    nullable=True, server_default="[]"),
        sa.Column("converted",          sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_unanswered_converted", "unanswered_questions", ["converted"])
    op.create_index("ix_unanswered_count",     "unanswered_questions", ["count"])

    # ── knowledge_documents (pgvector) ────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id",          sa.String(), primary_key=True, nullable=False),
        sa.Column("source_id",   sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("content",     sa.Text(),   nullable=False),
        sa.Column("embedding",   Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("created_at",  sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_source_id", "knowledge_documents", ["source_id"])

    # Índice HNSW para busca por similaridade coseno (mais rápido que IVFFlat)
    op.execute(f"""
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw")
    op.drop_table("knowledge_documents")
    op.drop_table("unanswered_questions")
    op.drop_table("interactions")
    op.drop_table("config")
    op.drop_table("events")
    op.drop_table("faqs")
