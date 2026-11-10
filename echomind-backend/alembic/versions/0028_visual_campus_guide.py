"""Adiciona referências, fotos e códigos públicos ao guia visual do campus.

Revision ID: 0028
Revises: 0027

Cadastros e dados de caminhos anteriores são preservados para a atualização.
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def _public_code():
    return sa.Column("public_code", sa.String(36), nullable=False,
                     server_default=sa.text("gen_random_uuid()::text"))


def upgrade() -> None:
    for table in ("campus_buildings", "campus_spaces"):
        # The database generates and retains one opaque code for every existing row.
        op.add_column(table, _public_code())
        op.create_unique_constraint(f"uq_{table}_public_code", table, ["public_code"])
    op.create_unique_constraint(
        "uq_campus_spaces_identity", "campus_spaces", ["id", "tenant_id", "campus_id"],
    )
    op.create_table(
        "campus_landmarks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("campus_id", sa.String(), nullable=False),
        _public_code(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("id", "tenant_id", "campus_id", name="uq_campus_landmarks_identity"),
        sa.UniqueConstraint("public_code", name="uq_campus_landmarks_public_code"),
        sa.UniqueConstraint("tenant_id", "campus_id", "name", name="uq_campus_landmarks_name"),
        sa.ForeignKeyConstraint(
            ["campus_id", "tenant_id"], ["campuses.id", "campuses.tenant_id"],
            name="fk_campus_landmarks_campus", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("lat BETWEEN -90 AND 90", name="ck_campus_landmarks_lat"),
        sa.CheckConstraint("lng BETWEEN -180 AND 180", name="ck_campus_landmarks_lng"),
    )
    op.create_index("ix_campus_landmarks_tenant_campus_active", "campus_landmarks",
                    ["tenant_id", "campus_id", "active"])

    op.create_table(
        "campus_place_photos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("campus_id", sa.String(), nullable=False),
        sa.Column("building_id", sa.String(), nullable=True),
        sa.Column("space_id", sa.String(), nullable=True),
        sa.Column("landmark_id", sa.String(), nullable=True),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(30), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        *[
            sa.ForeignKeyConstraint(
                [f"{place_type}_id", "tenant_id", "campus_id"],
                [f"{parent}.id", f"{parent}.tenant_id", f"{parent}.campus_id"],
                name=f"fk_campus_photos_{place_type}", ondelete="CASCADE",
            )
            for place_type, parent in (
                ("building", "campus_buildings"), ("space", "campus_spaces"),
                ("landmark", "campus_landmarks"),
            )
        ],
        sa.CheckConstraint(
            "(CASE WHEN building_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN space_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN landmark_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_campus_photos_one_place",
        ),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 5242880", name="ck_campus_photos_size"),
        sa.CheckConstraint("sort_order >= 0", name="ck_campus_photos_order"),
        sa.UniqueConstraint("building_id", "sha256", name="uq_campus_photos_building_digest"),
        sa.UniqueConstraint("space_id", "sha256", name="uq_campus_photos_space_digest"),
        sa.UniqueConstraint("landmark_id", "sha256", name="uq_campus_photos_landmark_digest"),
    )
    op.create_index("ix_campus_photos_tenant_campus", "campus_place_photos", ["tenant_id", "campus_id"])
    for table in ("campus_landmarks", "campus_place_photos"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM PUBLIC")
        for role in ("anon", "authenticated"):
            op.execute(f"""
                DO $$ BEGIN
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                        REVOKE ALL PRIVILEGES ON TABLE public.{table} FROM {role};
                    END IF;
                END $$;
            """)


def downgrade() -> None:
    op.drop_table("campus_place_photos")
    op.drop_table("campus_landmarks")
    op.drop_constraint("uq_campus_spaces_identity", "campus_spaces", type_="unique")
    for table in ("campus_spaces", "campus_buildings"):
        op.drop_constraint(f"uq_{table}_public_code", table, type_="unique")
        op.drop_column(table, "public_code")
