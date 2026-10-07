"""Mapas geográficos, prédios, espaços e caminhos por instituição.

Revision ID: 0021
Revises: 0020
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _identity_columns():
    return (
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
    )


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def _campus_fk(table_name: str):
    return sa.ForeignKeyConstraint(
        ["campus_id", "tenant_id"], ["campuses.id", "campuses.tenant_id"],
        name=f"fk_{table_name}_campus", ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "campuses",
        *_identity_columns(),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lng", sa.Float(), nullable=False),
        sa.Column("zoom", sa.Integer(), nullable=False, server_default="17"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("id", "tenant_id", name="uq_campuses_id_tenant"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_campuses_tenant_name"),
        sa.CheckConstraint("center_lat BETWEEN -90 AND 90", name="ck_campuses_lat"),
        sa.CheckConstraint("center_lng BETWEEN -180 AND 180", name="ck_campuses_lng"),
        sa.CheckConstraint("zoom BETWEEN 1 AND 22", name="ck_campuses_zoom"),
    )
    op.create_index("ix_campuses_tenant_active", "campuses", ["tenant_id", "active"])

    op.create_table(
        "campus_path_nodes",
        *_identity_columns(),
        sa.Column("campus_id", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("id", "tenant_id", "campus_id", name="uq_campus_path_nodes_identity"),
        _campus_fk("campus_path_nodes"),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name="ck_campus_path_nodes_lat"),
        sa.CheckConstraint("lng BETWEEN -180 AND 180", name="ck_campus_path_nodes_lng"),
    )
    op.create_index("ix_campus_path_nodes_tenant_campus", "campus_path_nodes", ["tenant_id", "campus_id"])

    op.create_table(
        "campus_buildings",
        *_identity_columns(),
        sa.Column("campus_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="predio"),
        sa.Column("entrance_lat", sa.Float(), nullable=False),
        sa.Column("entrance_lng", sa.Float(), nullable=False),
        sa.Column("entrance_node_id", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("id", "tenant_id", "campus_id", name="uq_campus_buildings_identity"),
        sa.UniqueConstraint("tenant_id", "campus_id", "name", name="uq_campus_buildings_name"),
        _campus_fk("campus_buildings"),
        sa.ForeignKeyConstraint(
            ["entrance_node_id", "tenant_id", "campus_id"],
            ["campus_path_nodes.id", "campus_path_nodes.tenant_id", "campus_path_nodes.campus_id"],
            name="fk_campus_buildings_entrance_node", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("entrance_lat BETWEEN -90 AND 90", name="ck_campus_buildings_lat"),
        sa.CheckConstraint("entrance_lng BETWEEN -180 AND 180", name="ck_campus_buildings_lng"),
    )
    op.create_index("ix_campus_buildings_tenant_campus_active", "campus_buildings", ["tenant_id", "campus_id", "active"])

    op.create_table(
        "campus_spaces",
        *_identity_columns(),
        sa.Column("campus_id", sa.String(), nullable=False),
        sa.Column("building_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False, server_default="outro"),
        sa.Column("floor", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "campus_id", "building_id", "name", name="uq_campus_spaces_name"),
        _campus_fk("campus_spaces"),
        sa.ForeignKeyConstraint(
            ["building_id", "tenant_id", "campus_id"],
            ["campus_buildings.id", "campus_buildings.tenant_id", "campus_buildings.campus_id"],
            name="fk_campus_spaces_building", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_campus_spaces_tenant_building_active", "campus_spaces", ["tenant_id", "building_id", "active"])

    op.create_table(
        "campus_path_edges",
        *_identity_columns(),
        sa.Column("campus_id", sa.String(), nullable=False),
        sa.Column("from_node_id", sa.String(), nullable=False),
        sa.Column("to_node_id", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("accessible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "campus_id", "from_node_id", "to_node_id", name="uq_campus_path_edges_pair"),
        _campus_fk("campus_path_edges"),
        sa.ForeignKeyConstraint(
            ["from_node_id", "tenant_id", "campus_id"],
            ["campus_path_nodes.id", "campus_path_nodes.tenant_id", "campus_path_nodes.campus_id"],
            name="fk_campus_path_edges_from", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_node_id", "tenant_id", "campus_id"],
            ["campus_path_nodes.id", "campus_path_nodes.tenant_id", "campus_path_nodes.campus_id"],
            name="fk_campus_path_edges_to", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("from_node_id < to_node_id", name="ck_campus_path_edges_order"),
        sa.CheckConstraint("distance_m IS NULL OR distance_m > 0", name="ck_campus_path_edges_distance"),
    )
    op.create_index("ix_campus_path_edges_tenant_campus_active", "campus_path_edges", ["tenant_id", "campus_id", "active"])

    for table in ("campuses", "campus_path_nodes", "campus_buildings", "campus_spaces", "campus_path_edges"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM authenticated';
                END IF;
            END $$;
        """)


def downgrade() -> None:
    for table in ("campus_path_edges", "campus_spaces", "campus_buildings", "campus_path_nodes", "campuses"):
        op.drop_table(table)
