"""Política de retenção no PostgreSQL descartável, sem dados reais."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Config, Interaction
from app.privacy_retention import run_configured_retention

pytestmark = pytest.mark.integration


def test_migration_defaults_and_retention_constraint(postgres_engine):
    with postgres_engine.connect() as connection, connection.begin():
        row = connection.execute(text(
            "INSERT INTO config (id, tenant_id, public_slug, company_name) "
            "VALUES ('privacy-default', 'privacy-default', 'privacy-default', 'Synthetic') "
            "RETURNING chat_retention_enabled, chat_retention_days, privacy_email"
        )).one()
        assert tuple(row) == (False, None, None)
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(text("UPDATE config SET chat_retention_days=0 WHERE id='privacy-default'"))
        assert connection.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid='public.config'::regclass")).scalar() is True
        connection.execute(text("DELETE FROM config WHERE id='privacy-default'"))


def test_scheduled_cleanup_is_tenant_scoped_on_postgresql(postgres_engine):
    tenants = ["privacy-active", "privacy-paused"]
    now = datetime.now(timezone.utc)
    factory = sessionmaker(bind=postgres_engine)
    try:
        with Session(postgres_engine) as db:
            for tenant, enabled in zip(tenants, [True, False]):
                db.add(Config(
                    tenant_id=tenant, public_slug=tenant, company_name="Synthetic",
                    privacy_controller="Synthetic", privacy_email="privacy@example.com",
                    privacy_purpose="Atendimento sintético", privacy_legal_basis="Teste sintético",
                    chat_retention_days=30, chat_retention_enabled=enabled,
                ))
                db.add_all([
                    Interaction(tenant_id=tenant, question="old synthetic", asked_at=now-timedelta(days=40)),
                    Interaction(tenant_id=tenant, question="recent synthetic", asked_at=now),
                ])
            db.commit()
        assert run_configured_retention(session_factory=factory, now=now) == 1
        with Session(postgres_engine) as db:
            assert db.query(Interaction).filter_by(tenant_id=tenants[0]).count() == 1
            assert db.query(Interaction).filter_by(tenant_id=tenants[1]).count() == 2
    finally:
        with Session(postgres_engine) as db:
            db.execute(delete(Interaction).where(Interaction.tenant_id.in_(tenants)))
            db.execute(delete(Config).where(Config.tenant_id.in_(tenants)))
            db.commit()
