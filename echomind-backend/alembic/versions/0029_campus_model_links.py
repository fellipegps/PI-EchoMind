"""Vincula campi e blocos aos dados publicados da maquete.

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("campuses", sa.Column("model_key", sa.String(80), nullable=True))
    op.add_column("campus_buildings", sa.Column("model_destination_id", sa.String(80), nullable=True))
    op.create_unique_constraint(
        "uq_campus_buildings_model_destination", "campus_buildings", ["tenant_id", "campus_id", "model_destination_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_campus_buildings_model_destination", "campus_buildings", type_="unique")
    op.drop_column("campus_buildings", "model_destination_id")
    op.drop_column("campuses", "model_key")
