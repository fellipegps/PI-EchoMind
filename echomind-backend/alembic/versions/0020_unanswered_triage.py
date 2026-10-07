"""Triagem e supressão por tenant das perguntas não respondidas.

Revision ID: 0020
Revises: 0019
"""

import json

from alembic import op
import sqlalchemy as sa

from app.unanswered_triage import classify_group_v1, question_fingerprint


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "unanswered_questions",
        sa.Column("triage_status", sa.String(length=16), nullable=False, server_default="pending"),
    )
    op.add_column(
        "unanswered_questions",
        sa.Column("triage_reason", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "unanswered_questions",
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_unanswered_triage_status",
        "unanswered_questions",
        "triage_status IN ('pending', 'review', 'ignored')",
    )
    op.create_index(
        "ix_unanswered_tenant_fingerprint",
        "unanswered_questions",
        ["tenant_id", "fingerprint"],
    )
    op.create_table(
        "unanswered_suppressions",
        sa.Column("tenant_id", sa.String(), primary_key=True),
        sa.Column("fingerprint", sa.String(length=64), primary_key=True),
        sa.Column("question_id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_unanswered_suppressions_tenant_question",
        "unanswered_suppressions",
        ["tenant_id", "question_id"],
    )
    op.execute("ALTER TABLE public.unanswered_suppressions ENABLE ROW LEVEL SECURITY")
    op.execute(
        """DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.unanswered_suppressions FROM anon';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.unanswered_suppressions FROM authenticated';
            END IF;
        END $$;"""
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT id, tenant_id, canonical_question, similar_questions "
        "FROM unanswered_questions"
    )).mappings().all()
    for row in rows:
        try:
            variants = json.loads(row["similar_questions"] or "[]")
        except (TypeError, ValueError):
            variants = []
        if not isinstance(variants, list):
            variants = []
        variants = [variant for variant in variants if isinstance(variant, str)]
        decision = classify_group_v1([row["canonical_question"], *variants])
        status = "ignored" if decision.status == "discard" else decision.status
        connection.execute(
            sa.text(
                "UPDATE unanswered_questions SET triage_status = :status, "
                "triage_reason = :reason, fingerprint = :fingerprint "
                "WHERE id = :id AND tenant_id IS NOT DISTINCT FROM :tenant_id"
            ),
            {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "status": status,
                "reason": decision.reason,
                "fingerprint": question_fingerprint(row["canonical_question"]),
            },
        )


def downgrade() -> None:
    op.drop_index(
        "ix_unanswered_suppressions_tenant_question",
        table_name="unanswered_suppressions",
    )
    op.drop_table("unanswered_suppressions")
    op.drop_index("ix_unanswered_tenant_fingerprint", table_name="unanswered_questions")
    op.drop_constraint("ck_unanswered_triage_status", "unanswered_questions", type_="check")
    op.drop_column("unanswered_questions", "fingerprint")
    op.drop_column("unanswered_questions", "triage_reason")
    op.drop_column("unanswered_questions", "triage_status")
