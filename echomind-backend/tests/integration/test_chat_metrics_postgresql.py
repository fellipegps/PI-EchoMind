"""A retenção do histórico não altera as métricas agregadas de atendimento."""
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.crud import get_dashboard_stats, save_feedback, save_interaction
from app.database import ChatMetricDaily, Interaction, utc_now
from app.privacy_retention import purge_chat_data


pytestmark = pytest.mark.integration


def test_backfill_and_live_counts_survive_removal_of_chat_history(postgres_engine):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    now = utc_now()
    tenant = "dashboard-metrics-synthetic"
    other = "dashboard-metrics-other"

    with postgres_engine.connect() as connection, connection.begin() as transaction:
        config.attributes["connection"] = connection
        command.downgrade(config, "0026")
        connection.execute(
            text("""
                INSERT INTO interactions (id, tenant_id, question, asked_at, feedback_helpful)
                VALUES (:id, :tenant, 'Pergunta sintética', :asked_at, :feedback)
            """),
            [
                {"id": f"{tenant}-{i}", "tenant": owner, "asked_at": now - timedelta(days=age), "feedback": feedback}
                for i, (owner, age, feedback) in enumerate([
                    (tenant, 3, None),
                    (tenant, 29, None),
                    (tenant, 30, None),
                    (tenant, 90, None),
                    (tenant, 3, True),
                    (tenant, 3, False),
                    (other, 3, None),
                    (None, 3, None),
                ])
            ],
        )
        connection.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    CREATE ROLE anon NOLOGIN;
                END IF;
            END;
            $$
        """))
        connection.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon"))
        command.upgrade(config, "head")
        # Legacy writers may still insert records without an institution.
        connection.execute(text("""
            INSERT INTO interactions (id, question, asked_at)
            VALUES ('legacy-metrics-sentinel', 'Pergunta legada', CURRENT_TIMESTAMP)
        """))

        assert connection.execute(text(
            "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.chat_metric_daily'::regclass"
        )).scalar_one()
        assert not connection.execute(text(
            "SELECT has_table_privilege('anon', 'public.chat_metric_daily', 'SELECT') "
            "OR has_function_privilege('anon', 'public.record_chat_metric()', 'EXECUTE')"
        )).scalar_one()

        with Session(connection) as db:
            assert db.get(ChatMetricDaily, (tenant, now.date() - timedelta(days=90))) is None
            assert db.get(ChatMetricDaily, (tenant, now.date() - timedelta(days=30))).question_count == 1
            assert save_interaction(db, "Outra dúvida", "Resposta sintética", tenant)
            save_feedback(db, "Outra dúvida", "Resposta sintética", True, tenant)
            before = get_dashboard_stats(db, tenant)
            assert before["metrics_window_days"] == 30
            assert before["total_questions"] == 3
            assert before["satisfaction_rate"] == 66.7
            assert [day["count"] for day in before["daily_interactions"]] == [0, 0, 0, 1, 0, 0, 1]

            assert purge_chat_data(db, tenant_id=tenant, cutoff=now - timedelta(days=1), apply=True)["interactions"] == 6
            assert db.query(Interaction).filter_by(tenant_id=tenant).count() == 2
            after = get_dashboard_stats(db, tenant)
            for key in ("total_questions", "satisfaction_rate", "daily_interactions"):
                assert after[key] == before[key]
            assert get_dashboard_stats(db, other)["total_questions"] == 1

        command.downgrade(config, "0026")
        assert connection.execute(text(
            "SELECT count(*) FROM interactions WHERE tenant_id = :tenant"
        ), {"tenant": tenant}).scalar_one() == 2
        transaction.rollback()
