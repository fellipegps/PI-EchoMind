"""Retira a tabela do mapa substituído pela navegação geográfica.

Revision ID: 0023
Revises: 0022

Aplicar esta revisão remove os registros da tabela retirada. O downgrade
recria somente a estrutura, índices e proteções; não recupera dados.
"""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("campus_locations")


def downgrade() -> None:
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

