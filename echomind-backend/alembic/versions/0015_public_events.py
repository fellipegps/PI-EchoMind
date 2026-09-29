"""Adiciona publicação e local aos eventos institucionais.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column(
            "location",
            sa.String(length=300),
            nullable=False,
            server_default="Local a definir",
        ),
    )
    op.add_column(
        "events",
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_events_tenant_published_date",
        "events",
        ["tenant_id", "published", "event_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_events_tenant_published_date", table_name="events")
    op.drop_column("events", "published")
    op.drop_column("events", "location")
