"""Informações públicas de privacidade e retenção opt-in por instituição.

Revision ID: 0024
Revises: 0023
"""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, length in (("privacy_controller", 200), ("privacy_email", 320), ("privacy_purpose", 1000), ("privacy_legal_basis", 1000)):
        op.add_column("config", sa.Column(name, sa.String(length), nullable=True))
    op.add_column("config", sa.Column("chat_retention_days", sa.Integer(), nullable=True))
    op.add_column("config", sa.Column("chat_retention_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_check_constraint("ck_config_chat_retention_days", "config", "chat_retention_days IS NULL OR chat_retention_days BETWEEN 1 AND 3650")


def downgrade() -> None:
    op.drop_constraint("ck_config_chat_retention_days", "config", type_="check")
    for name in ("chat_retention_enabled", "chat_retention_days", "privacy_legal_basis", "privacy_purpose", "privacy_email", "privacy_controller"):
        op.drop_column("config", name)
