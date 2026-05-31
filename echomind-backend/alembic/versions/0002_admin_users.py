"""Cria tabela admin_users para autenticação do painel

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-02 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id",              sa.String(),  primary_key=True),
        sa.Column("email",           sa.String(),  nullable=False),
        sa.Column("hashed_password", sa.String(),  nullable=False),
        sa.Column("is_active",       sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_table("admin_users")
