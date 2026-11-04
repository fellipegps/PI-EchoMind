"""Real PostgreSQL transactions/locks; no providers or production data."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.database import Interaction, UnansweredQuestion
from app.unanswered_handoff import InvalidHandoff, new_handoff, submit_unanswered

pytestmark = pytest.mark.integration


def test_concurrent_confirmation_is_atomic_tenant_scoped_and_retryable(postgres_engine):
    tenant = "handoff-concurrent"
    token, digest = new_handoff()
    try:
        with Session(postgres_engine) as db:
            db.add(Interaction(tenant_id=tenant, question="Qual é o prazo de matrícula?", answer="Não tenho informações.", was_answered=False, unanswered_token_hash=digest))
            db.commit()
        with Session(postgres_engine) as db:
            with pytest.raises(InvalidHandoff):
                submit_unanswered(db, tenant_id="another-institution", token=token)
            db.rollback()
        with Session(postgres_engine) as db:
            from app.rag_engine import register_unanswered_question

            def fail_after_queue_write(question, owner, session):
                register_unanswered_question(question, owner, session)
                session.flush()
                raise RuntimeError("synthetic persistence failure")

            with patch("app.rag_engine.register_unanswered_question", side_effect=fail_after_queue_write), pytest.raises(RuntimeError):
                submit_unanswered(db, tenant_id=tenant, token=token)
            db.rollback()
            assert db.query(UnansweredQuestion).filter_by(tenant_id=tenant).count() == 0
            assert db.query(Interaction).filter_by(tenant_id=tenant).one().unanswered_submitted_at is None

        barrier = Barrier(2)

        def confirm():
            with Session(postgres_engine) as db:
                barrier.wait(timeout=10)
                submit_unanswered(db, tenant_id=tenant, token=token)
                db.commit()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(confirm) for _ in range(2)]
            for future in futures:
                future.result(timeout=15)
        with Session(postgres_engine) as db:
            assert db.query(UnansweredQuestion).filter_by(tenant_id=tenant).one().count == 1
            assert db.query(Interaction).filter_by(tenant_id=tenant).one().unanswered_submitted_at is not None
    finally:
        with Session(postgres_engine) as db:
            db.execute(delete(UnansweredQuestion).where(UnansweredQuestion.tenant_id == tenant))
            db.execute(delete(Interaction).where(Interaction.tenant_id == tenant))
            db.commit()


def test_handoff_migration_is_additive_and_reversible(postgres_engine):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    with postgres_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0025")
        connection.execute(text("INSERT INTO interactions (id,tenant_id,question,was_answered,asked_at) VALUES ('handoff-sentinel','handoff-sentinel','Synthetic question',false,NOW())"))
        command.upgrade(config, "head")
        row = connection.execute(text("SELECT question,unanswered_token_hash,unanswered_submitted_at FROM interactions WHERE id='handoff-sentinel'")).one()
        assert tuple(row) == ("Synthetic question", None, None)
        assert connection.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid='public.interactions'::regclass")).scalar() is True
        assert connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('anon','authenticated') AND has_table_privilege(oid,'public.interactions','SELECT'))")).scalar() is False
        command.downgrade(config, "0025")
        assert connection.execute(text("SELECT question FROM interactions WHERE id='handoff-sentinel'")).scalar() == "Synthetic question"
        command.upgrade(config, "head")
        connection.execute(text("DELETE FROM interactions WHERE id='handoff-sentinel'"))
