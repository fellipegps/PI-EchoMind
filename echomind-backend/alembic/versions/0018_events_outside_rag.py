"""Move events out of the knowledge base.

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("event_end_date", sa.String(), nullable=True))
    op.add_column("events", sa.Column("image_url", sa.String(length=2000), nullable=True))
    op.add_column("events", sa.Column("link_url", sa.String(length=2000), nullable=True))
    op.execute("UPDATE events SET event_end_date = event_date")
    op.alter_column(
        "events",
        "event_end_date",
        existing_type=sa.String(),
        nullable=False,
    )
    op.drop_index("ix_events_tenant_published_date", table_name="events")
    op.drop_index("ix_events_fts_portuguese", table_name="events")
    op.drop_column("events", "published")
    op.create_index(
        "ix_events_tenant_end_date",
        "events",
        ["tenant_id", "event_end_date"],
    )

    # PGVector usa cmetadata JSONB nesta instalação. O operador ->> também
    # funciona com JSON; to_regclass mantém a migration segura antes do runtime.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.langchain_pg_embedding') IS NOT NULL THEN
                DELETE FROM public.langchain_pg_embedding
                WHERE cmetadata->>'source_type' = 'event';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.drop_index("ix_events_tenant_end_date", table_name="events")
    op.add_column(
        "events",
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.create_index(
        "ix_events_tenant_published_date",
        "events",
        ["tenant_id", "published", "event_date"],
    )
    op.execute(
        "CREATE INDEX ix_events_fts_portuguese ON public.events USING gin "
        "(to_tsvector('portuguese', "
        "coalesce(title, '') || ' ' || coalesce(event_date, '') || ' ' || "
        "coalesce(event_type, '') || ' ' || coalesce(description, '')))"
    )
    op.drop_column("events", "link_url")
    op.drop_column("events", "image_url")
    op.drop_column("events", "event_end_date")
