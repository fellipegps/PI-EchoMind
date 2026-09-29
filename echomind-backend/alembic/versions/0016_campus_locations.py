"""Cria locais esquemáticos do campus com isolamento por tenant.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campus_locations",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.String(length=100),
            nullable=False,
            server_default="outro",
        ),
        sa.Column("floor", sa.String(length=50), nullable=True),
        sa.Column("building", sa.String(length=100), nullable=True),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
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
            name="uq_campus_locations_tenant_name",
        ),
        sa.CheckConstraint(
            "x >= 0 AND x <= 100",
            name="ck_campus_locations_x_range",
        ),
        sa.CheckConstraint(
            "y >= 0 AND y <= 100",
            name="ck_campus_locations_y_range",
        ),
    )
    op.create_index(
        "ix_campus_locations_tenant_id",
        "campus_locations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_campus_locations_tenant_active_name",
        "campus_locations",
        ["tenant_id", "active", "name"],
    )
    op.execute(
        "ALTER TABLE public.campus_locations ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.campus_locations FROM anon';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.campus_locations FROM authenticated';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_table("campus_locations")
