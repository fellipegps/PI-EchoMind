"""Acesso e eliminação selecionados em PostgreSQL descartável, sem dados reais."""
import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_selected_export_deletion_and_rollback_preserve_other_tenants(postgres_engine):
    from app.database import Interaction
    from app.privacy_requests import delete_chat_records, export_chat_records

    tenants = ["privacy-request-a", "privacy-request-b"]
    try:
        with Session(postgres_engine) as db:
            db.add_all([
                Interaction(id="privacy-request-a1", tenant_id=tenants[0], question="Synthetic question", answer="Synthetic answer"),
                Interaction(id="privacy-request-b1", tenant_id=tenants[1], question="Synthetic question"),
            ])
            db.commit()
        with Session(postgres_engine) as db:
            export = export_chat_records(db, tenant_id=tenants[0], interaction_ids=["privacy-request-a1"])
            assert [row["id"] for row in export["interactions"]] == ["privacy-request-a1"]
            with pytest.raises(ValueError):
                delete_chat_records(db, tenant_id=tenants[0], interaction_ids=["privacy-request-a1", "privacy-request-b1"], apply=True)
            assert delete_chat_records(db, tenant_id=tenants[0], interaction_ids=["privacy-request-a1"], apply=True) == 1
            db.rollback()
        with Session(postgres_engine) as db:
            assert db.query(Interaction).filter(Interaction.tenant_id.in_(tenants)).count() == 2
            assert delete_chat_records(db, tenant_id=tenants[0], interaction_ids=["privacy-request-a1"], apply=True) == 1
            db.commit()
        with Session(postgres_engine) as db:
            assert db.query(Interaction).filter_by(tenant_id=tenants[0]).count() == 0
            assert db.query(Interaction).filter_by(tenant_id=tenants[1]).count() == 1
    finally:
        with Session(postgres_engine) as db:
            db.execute(delete(Interaction).where(Interaction.tenant_id.in_(tenants)))
            db.commit()
