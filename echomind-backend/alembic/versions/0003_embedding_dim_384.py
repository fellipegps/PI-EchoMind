"""atualiza embedding dim para 384

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw")
    op.execute("TRUNCATE TABLE knowledge_documents")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        """
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_knowledge_embedding_hnsw")
    op.execute("TRUNCATE TABLE knowledge_documents")
    op.execute("ALTER TABLE knowledge_documents ALTER COLUMN embedding TYPE vector(768)")
    op.execute(
        """
        CREATE INDEX ix_knowledge_embedding_hnsw
        ON knowledge_documents
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
