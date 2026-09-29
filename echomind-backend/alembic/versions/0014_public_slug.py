"""Adiciona identificador publico unico para instituicoes.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "config",
        sa.Column("public_slug", sa.String(length=100), nullable=True),
    )
    op.execute(
        """
        WITH normalized AS (
            SELECT
                id,
                COALESCE(
                    NULLIF(
                        trim(BOTH '-' FROM regexp_replace(
                            translate(
                                lower(COALESCE(company_name, '')),
                                'áàãâäéèêëíìîïóòõôöúùûüçñ',
                                'aaaaaeeeeiiiiooooouuuucn'
                            ),
                            '[^a-z0-9]+',
                            '-',
                            'g'
                        )),
                        ''
                    ),
                    'instituicao'
                ) AS base_slug,
                substr(md5(COALESCE(tenant_id, id)), 1, 16) AS tenant_hash
            FROM config
        )
        UPDATE config AS target
        SET public_slug =
            left(normalized.base_slug, 83) || '-' || normalized.tenant_hash
        FROM normalized
        WHERE normalized.id = target.id
        """
    )
    op.alter_column("config", "public_slug", nullable=False)
    op.create_unique_constraint(
        "uq_config_public_slug",
        "config",
        ["public_slug"],
    )
    op.create_check_constraint(
        "ck_config_public_slug_length",
        "config",
        "length(public_slug) BETWEEN 3 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_config_public_slug_length",
        "config",
        type_="check",
    )
    op.drop_constraint(
        "uq_config_public_slug",
        "config",
        type_="unique",
    )
    op.drop_column("config", "public_slug")
