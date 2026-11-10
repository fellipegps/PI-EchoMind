import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.database import Config, Interaction, UnansweredQuestion, UnansweredSuppression
from app.privacy_retention import retention_worker, run_configured_retention


@pytest.mark.parametrize("mode", ["development", "testing", "production"])
def test_public_chat_works_without_privacy_policy_in_every_mode(client, monkeypatch, mode):
    monkeypatch.setenv("ECHOMIND_ENV", mode)
    config = client.get("/config").json()
    assert config["privacy_ready"] is False
    assert config["chat_retention_enabled"] is True
    assert config["chat_retention_days"] == 30
    response = client.post(f"/public/{config['public_slug']}/chat", json={"message": "Onde fica a secretaria?"})
    assert response.status_code == 200
    assert "Onde fica a secretaria?" in response.text
    assert client.get(f"/public/{config['public_slug']}/events").status_code == 200


def test_configuration_is_public_safe(client, privacy_config_data):
    response = client.put("/config", json=privacy_config_data)
    assert response.status_code == 200
    config = response.json()
    assert config["privacy_ready"] is True
    public = client.get(f"/public/{config['public_slug']}").json()
    assert public["privacy_email"] == privacy_config_data["privacy_email"]
    assert "tenant_id" not in public and "id" not in public
    assert client.put("/config", json={"company_name": "Nome atualizado"}).json()["privacy_ready"] is True
    assert public["chat_retention_days"] == 30 and public["chat_retention_enabled"] is True


def test_partial_notice_keeps_public_chat_and_cleanup_available(client, db, privacy_config_data):
    draft = {**privacy_config_data, "privacy_controller": "UniEVANGÉLICA"}
    draft.pop("privacy_legal_basis")
    response = client.put("/config", json=draft)
    assert response.status_code == 200
    saved = response.json()
    assert saved["chat_retention_days"] == 30 and saved["privacy_legal_basis"] is None
    assert saved["privacy_ready"] is False and saved["chat_retention_enabled"] is True
    db.add(Interaction(tenant_id="test-admin", question="Synthetic old question", asked_at=datetime.now(timezone.utc) - timedelta(days=45)))
    db.commit()
    assert run_configured_retention(session_factory=sessionmaker(bind=db.connection()))["interactions"] == 1
    assert db.query(Interaction).filter_by(tenant_id="test-admin").count() == 0
    response = client.post(f"/public/{saved['public_slug']}/chat", json={"message": "Onde fica a secretaria?"})
    assert response.status_code == 200
    assert "Onde fica a secretaria?" in response.text


@pytest.mark.parametrize("changes", [
    {"privacy_email": "invalid"}, {"privacy_email": "safe@example.test\r\nBcc:private@example.test"},
])
def test_invalid_privacy_email_is_rejected(client, changes):
    assert client.put("/config", json=changes).status_code == 422


def test_editing_notice_does_not_pause_cleanup(client, privacy_config_data):
    assert client.put("/config", json=privacy_config_data).status_code == 200
    response = client.put("/config", json={"privacy_email": "  "})
    assert response.status_code == 200
    assert response.json()["privacy_ready"] is False
    assert response.json()["chat_retention_enabled"] is True


@pytest.mark.parametrize("requested_days", [1, 3650, 99999, None])
def test_admin_payload_cannot_change_server_retention(client, db, monkeypatch, requested_days):
    monkeypatch.setenv("CHAT_HISTORY_RETENTION_DAYS", "14")
    response = client.put("/config", json={
        "chat_retention_days": requested_days, "chat_retention_enabled": False,
    })
    assert response.status_code == 200
    config = response.json()
    assert config["chat_retention_days"] == 14
    assert config["chat_retention_enabled"] is True
    public = client.get(f"/public/{config['public_slug']}").json()
    assert public["chat_retention_days"] == 14 and public["chat_retention_enabled"] is True
    stored = db.query(Config).filter_by(tenant_id="test-admin").one()
    assert stored.chat_retention_days is None and stored.chat_retention_enabled is False


def test_configuration_does_not_modify_other_tenants(client, db, privacy_config_data):
    other = Config(tenant_id="other", public_slug="other", company_name="Outra instituição")
    db.add(other); db.flush()
    client.put("/config", json=privacy_config_data)
    db.refresh(other)
    assert other.privacy_email is None and other.chat_retention_enabled is False


def test_scheduled_retention_uses_operator_cutoff_for_all_institutions(db, privacy_config_data, monkeypatch):
    monkeypatch.setenv("CHAT_HISTORY_RETENTION_DAYS", "14")
    now = datetime.now(timezone.utc)
    db.add(Config(
        tenant_id="active", public_slug="active", company_name="Active", **privacy_config_data,
        chat_retention_enabled=True, chat_retention_days=3650,
    ))
    db.add(Config(tenant_id="incomplete", public_slug="incomplete", company_name="Incomplete"))
    for tenant in ("active", "incomplete", "legacy"):
        db.add(Interaction(tenant_id=tenant, question="old", asked_at=now - timedelta(days=15)))
        db.add(Interaction(tenant_id=tenant, question="at cutoff", asked_at=now - timedelta(days=14)))
    question = UnansweredQuestion(
        tenant_id="incomplete", canonical_question="old triage", first_asked=now - timedelta(days=15),
    )
    db.add(question)
    db.flush()
    db.add(UnansweredSuppression(
        tenant_id="incomplete", question_id=question.id, fingerprint="fixture", created_at=now,
    ))
    db.flush()
    factory = sessionmaker(bind=db.connection())
    assert run_configured_retention(session_factory=factory, now=now) == {
        "interactions": 3, "unanswered": 1, "suppressions": 1,
    }
    assert [row.question for row in db.query(Interaction).all()] == ["at cutoff"] * 3


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
