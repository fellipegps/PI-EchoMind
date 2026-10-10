"""Impede documentos ativos com o mesmo hash no mesmo tenant.

Revision ID: 0022
Revises: 0021
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bloqueia escritas entre o diagnostico e a criacao do indice. O DDL e a
    # verificacao participam da mesma transacao PostgreSQL, inclusive em --sql.
    op.execute("LOCK TABLE documents IN SHARE ROW EXCLUSIVE MODE")
    op.execute("""
        DO $$
        DECLARE
            conflicts text;
        BEGIN
            SELECT string_agg(
                format('tenant_id=%s sha256=%s ids=[%s] (grupos=%s)',
                       tenant_id, sha256, ids, group_count), E'\n'
            ) INTO conflicts
            FROM (
                SELECT tenant_id, sha256, string_agg(id, ', ' ORDER BY id) AS ids,
                       count(*) OVER () AS group_count
                FROM documents
                WHERE status IN ('pending', 'processing', 'ready')
                GROUP BY tenant_id, sha256
                HAVING count(*) > 1
                ORDER BY tenant_id, sha256
                LIMIT 10
            ) duplicates;
            IF conflicts IS NOT NULL THEN
                RAISE EXCEPTION USING
                    MESSAGE = 'Documentos ativos duplicados impedem a migration 0022.',
                    DETAIL = conflicts,
                    HINT = 'Nenhum registro foi removido. Reconcilie manualmente os grupos indicados antes de tentar novamente.';
            END IF;
        END $$;
    """)
    op.create_index(
        "uq_documents_active_tenant_sha256", "documents", ["tenant_id", "sha256"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'processing', 'ready')"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_active_tenant_sha256", table_name="documents")
