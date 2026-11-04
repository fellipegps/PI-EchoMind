"""Remove privilégios diretos de clientes nas tabelas exclusivas do backend.

Revision ID: 0025
Revises: 0024
"""
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

TABLES = (
    "alembic_version", "config", "faqs", "events", "event_courses",
    "interactions", "unanswered_questions", "unanswered_suppressions",
    "documents", "document_chunks", "document_chunk_parents", "rag_metric_daily",
    "campuses", "campus_buildings", "campus_spaces", "campus_path_nodes", "campus_path_edges",
    "langchain_pg_collection", "langchain_pg_embedding",
)


def upgrade() -> None:
    for table in TABLES:
        # Names are a fixed allowlist. Do not affect Auth, Storage or extension functions.
        op.execute(f"""
            DO $$ BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC;
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                        REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM anon;
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                        REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM authenticated;
                    END IF;
                END IF;
            END $$;
        """)
    # PGVector may create its legacy tables lazily with the same backend role.
    # Secure future tables of the migration owner as well as those already present.
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC")
    for role in ("anon", "authenticated"):
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {role};
                END IF;
            END $$;
        """)


def downgrade() -> None:
    # Previous releases also use the backend connection. Preserve least privilege;
    # the exact previous grants differ by installation and must not be invented.
    pass
