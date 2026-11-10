"""Agrega métricas de atendimento independentemente do histórico do chat.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_metric_daily",
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("question_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("positive_feedback_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("negative_feedback_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("tenant_id", "metric_date"),
        sa.CheckConstraint(
            "question_count >= 0 AND positive_feedback_count >= 0 AND negative_feedback_count >= 0",
            name="ck_chat_metric_daily_counts_nonnegative",
        ),
    )
    op.create_index("ix_chat_metric_daily_metric_date", "chat_metric_daily", ["metric_date"])
    op.execute("ALTER TABLE public.chat_metric_daily ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE FUNCTION public.record_chat_metric() RETURNS trigger
        LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
        AS $$
        BEGIN
            INSERT INTO public.chat_metric_daily AS metric
                (tenant_id, metric_date, question_count, positive_feedback_count, negative_feedback_count)
            VALUES (
                NEW.tenant_id,
                NEW.asked_at::date,
                CASE WHEN NEW.feedback_helpful IS NULL THEN 1 ELSE 0 END,
                CASE WHEN NEW.feedback_helpful IS TRUE THEN 1 ELSE 0 END,
                CASE WHEN NEW.feedback_helpful IS FALSE THEN 1 ELSE 0 END
            )
            ON CONFLICT (tenant_id, metric_date) DO UPDATE SET
                question_count = metric.question_count + EXCLUDED.question_count,
                positive_feedback_count = metric.positive_feedback_count + EXCLUDED.positive_feedback_count,
                negative_feedback_count = metric.negative_feedback_count + EXCLUDED.negative_feedback_count;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("REVOKE ALL PRIVILEGES ON TABLE public.chat_metric_daily FROM PUBLIC")
    op.execute("REVOKE EXECUTE ON FUNCTION public.record_chat_metric() FROM PUBLIC")
    op.execute("""
        DO $$
        DECLARE client_role text;
        BEGIN
            FOR client_role IN SELECT rolname FROM pg_roles
                WHERE rolname IN ('anon', 'authenticated', 'service_role')
            LOOP
                EXECUTE format('REVOKE ALL ON TABLE public.chat_metric_daily FROM %I', client_role);
                EXECUTE format('REVOKE EXECUTE ON FUNCTION public.record_chat_metric() FROM %I', client_role);
            END LOOP;
        END;
        $$
    """)
    # CREATE TRIGGER blocks concurrent writes until the transaction ends.
    # Backfill and live inserts meet at one boundary even with the old API running.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("""
        CREATE TRIGGER interactions_chat_metrics
        AFTER INSERT ON public.interactions
        FOR EACH ROW WHEN (NEW.tenant_id IS NOT NULL)
        EXECUTE FUNCTION public.record_chat_metric()
    """)
    op.execute("""
        INSERT INTO public.chat_metric_daily
            (tenant_id, metric_date, question_count, positive_feedback_count, negative_feedback_count)
        SELECT tenant_id, asked_at::date,
            COUNT(*) FILTER (WHERE feedback_helpful IS NULL),
            COUNT(*) FILTER (WHERE feedback_helpful IS TRUE),
            COUNT(*) FILTER (WHERE feedback_helpful IS FALSE)
        FROM public.interactions
        WHERE tenant_id IS NOT NULL
          AND asked_at >= (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date - 89
          AND asked_at < (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date + 1
        GROUP BY tenant_id, asked_at::date
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER interactions_chat_metrics ON public.interactions")
    op.execute("DROP FUNCTION public.record_chat_metric()")
    op.drop_table("chat_metric_daily")
