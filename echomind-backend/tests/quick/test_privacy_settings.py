import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Config, Interaction
from app.privacy_retention import retention_worker, run_configured_retention


def test_privacy_starts_disabled_and_blocks_public_chat_before_processing(client):
    config = client.get("/config").json()
    assert config["privacy_ready"] is False
    assert config["chat_retention_enabled"] is False
    with patch("app.main.get_rag_engine") as rag:
        response = client.post(f"/public/{config['public_slug']}/chat", json={"message": "Pergunta pessoal"})
    assert response.status_code == 503
    rag.assert_not_called()
    assert client.get(f"/public/{config['public_slug']}/events").status_code == 200


def test_configuration_is_public_safe_and_can_be_paused(client, privacy_config_data):
    response = client.put("/config", json=privacy_config_data)
    assert response.status_code == 200
    config = response.json()
    assert config["privacy_ready"] is True
    public = client.get(f"/public/{config['public_slug']}").json()
    assert public["privacy_email"] == privacy_config_data["privacy_email"]
    assert "tenant_id" not in public and "id" not in public
    assert client.put("/config", json={"company_name": "Nome atualizado"}).json()["privacy_ready"] is True
    assert client.put("/config", json={"chat_retention_enabled": False}).json()["privacy_ready"] is False


def test_partial_thirty_day_policy_can_be_saved_without_enabling_chat_or_cleanup(client, db, privacy_config_data):
    draft = {**privacy_config_data, "privacy_controller": "UniEVANGÉLICA", "chat_retention_days": 30, "chat_retention_enabled": False}
    draft.pop("privacy_legal_basis")
    response = client.put("/config", json=draft)
    assert response.status_code == 200
    saved = response.json()
    assert saved["chat_retention_days"] == 30 and saved["privacy_legal_basis"] is None
    assert saved["privacy_ready"] is False and saved["chat_retention_enabled"] is False
    db.add(Interaction(tenant_id="test-admin", question="Synthetic old question", asked_at=datetime.now(timezone.utc) - timedelta(days=45)))
    db.commit()
    assert run_configured_retention(session_factory=sessionmaker(bind=db.connection())) == 0
    assert db.query(Interaction).filter_by(tenant_id="test-admin").count() == 1
    with patch("app.main.get_rag_engine") as rag:
        assert client.post(f"/public/{saved['public_slug']}/chat", json={"message": "Onde fica a secretaria?"}).status_code == 503
    rag.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"privacy_email": "invalid"}, {"privacy_email": "safe@example.test\r\nBcc:private@example.test"},
    {"chat_retention_days": 0}, {"chat_retention_days": 3651}, {"chat_retention_days": 2.5},
    {"chat_retention_days": True}, {"chat_retention_enabled": True},
])
def test_invalid_or_incomplete_policy_is_rejected(client, changes):
    assert client.put("/config", json=changes).status_code == 422


def test_active_policy_cannot_have_required_field_removed(client, privacy_config_data):
    assert client.put("/config", json=privacy_config_data).status_code == 200
    assert client.put("/config", json={"privacy_email": "  "}).status_code == 422
    assert client.put("/config", json={"chat_retention_enabled": False, "privacy_email": None}).status_code == 200


def test_configuration_does_not_modify_other_tenants(client, db, privacy_config_data):
    other = Config(tenant_id="other", public_slug="other", company_name="Outra instituição")
    db.add(other); db.flush()
    client.put("/config", json=privacy_config_data)
    db.refresh(other)
    assert other.privacy_email is None and other.chat_retention_enabled is False


def test_scheduled_retention_only_applies_complete_enabled_policies(db, privacy_config_data):
    now = datetime.now(timezone.utc)
    for tenant, enabled, complete in [("active", True, True), ("paused", False, True), ("incomplete", True, False)]:
        policy = {**privacy_config_data, "chat_retention_enabled": enabled}
        if not complete:
            policy["privacy_email"] = None
        db.add(Config(tenant_id=tenant, public_slug=tenant, company_name=tenant, **policy))
        db.add(Interaction(tenant_id=tenant, question="old", asked_at=now - timedelta(days=40)))
        db.add(Interaction(tenant_id=tenant, question="recent", asked_at=now))
    db.flush()
    factory = sessionmaker(bind=db.connection())
    assert run_configured_retention(session_factory=factory, now=now) == 1
    assert db.query(Interaction).filter_by(tenant_id="active").count() == 1
    assert db.query(Interaction).filter_by(tenant_id="paused").count() == 2
    assert db.query(Interaction).filter_by(tenant_id="incomplete").count() == 2


async def test_retention_shutdown_before_first_interval_does_not_delete():
    stop = asyncio.Event()
    stop.set()
    with patch("app.privacy_retention.run_configured_retention") as cleanup:
        await retention_worker(stop, interval_seconds=0.01)
    cleanup.assert_not_called()


async def test_retention_worker_runs_and_stops_cleanly():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    def cleanup():
        loop.call_soon_threadsafe(stop.set)

    with patch("app.privacy_retention.run_configured_retention", side_effect=cleanup) as run:
        await asyncio.wait_for(retention_worker(stop, interval_seconds=0.01), timeout=2)
    run.assert_called_once_with()
