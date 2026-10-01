"""Add tenant event courses and relate events by course name.

Revision ID: 0019
Revises: 0018
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_courses",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_event_courses_tenant_name",
        ),
    )
    op.create_index(
        "ix_event_courses_tenant_name",
        "event_courses",
        ["tenant_id", "name"],
    )
    op.execute("ALTER TABLE public.event_courses ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.event_courses FROM anon';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.event_courses FROM authenticated';
            END IF;
        END $$;
        """
    )

    op.add_column(
        "events",
        sa.Column("course", sa.String(length=200), nullable=True),
    )
    op.execute("UPDATE events SET course = 'Geral'")
    op.alter_column(
        "events",
        "course",
        existing_type=sa.String(length=200),
        nullable=False,
        server_default="Geral",
    )
    op.create_index(
        "ix_events_tenant_course_date",
        "events",
        ["tenant_id", "course", "event_date"],
    )

    op.execute(
        """
        INSERT INTO event_courses (id, tenant_id, name, created_at, updated_at)
        SELECT md5(tenant_id || '-event-course-Geral'), tenant_id, 'Geral', now(), now()
        FROM (
            SELECT tenant_id FROM config
            UNION
            SELECT tenant_id FROM events
        ) AS tenants
        """
    )


def downgrade() -> None:
    op.drop_index("ix_events_tenant_course_date", table_name="events")
    op.drop_column("events", "course")
    op.drop_table("event_courses")
