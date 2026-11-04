"""Regressões de acesso e privacidade sem serviços externos."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.database import Interaction, UnansweredQuestion, UnansweredSuppression
from app.privacy_retention import purge_chat_data


LEGACY_REQUESTS = [
    ("POST", "/chat", {"message": "Onde fica a secretaria?", "tenant_id": "other-tenant"}),
    ("GET", "/config/public?tenant_id=other-tenant", None),
    ("GET", "/faqs/chatbot?tenant_id=other-tenant", None),
    ("POST", "/feedback", {"question": "Pergunta de teste", "answer": "Resposta de teste", "helpful": True, "tenant_id": "other-tenant"}),
]


@pytest.mark.parametrize("method,path,payload", LEGACY_REQUESTS)
def test_legacy_routes_reject_other_tenants(client, method, path, payload):
    response = client.request(method, path, json=payload)
    assert response.status_code == 403
    assert response.json() == {"detail": "Acesso não permitido."}


@pytest.mark.parametrize("method,path,payload", LEGACY_REQUESTS)
def test_legacy_routes_require_login(client, quick_test_context, method, path, payload):
    app = quick_test_context.app
    override = app.dependency_overrides.pop(quick_test_context.get_current_user)
    try:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    finally:
        app.dependency_overrides[quick_test_context.get_current_user] = override


def test_ai_initialization_never_exposes_exception_details(client, caplog, privacy_config_data):
    slug = client.put("/config", json=privacy_config_data).json()["public_slug"]
    with patch("app.main.get_rag_engine", side_effect=RuntimeError("secret-key and personal data")):
        response = client.post(f"/public/{slug}/chat", json={"message": "Onde fica a secretaria?"})
    assert response.status_code == 503
    assert "secret-key" not in response.text
    assert "secret-key" not in caplog.text
    assert response.headers["cache-control"] == "no-store"


def test_public_portal_works_without_login_and_logs_no_ip_or_slug(client, quick_test_context, caplog, privacy_config_data):
    slug = client.put("/config", json=privacy_config_data).json()["public_slug"]
    app = quick_test_context.app
    override = app.dependency_overrides.pop(quick_test_context.get_current_user)
    caplog.clear()
    try:
        with caplog.at_level("INFO", logger="echomind.middleware"):
            response = client.get(f"/public/{slug}?email=private@example.test")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        logs = " ".join(r.message for r in caplog.records if r.name == "echomind.middleware")
        assert "/public/{public_slug}" in logs
        assert slug not in logs
        assert "private@example.test" not in logs
        assert "testclient" not in logs
        chat = client.post(f"/public/{slug}/chat", json={"message": "Onde fica a secretaria?"})
        assert chat.status_code == 200
        assert chat.headers["cache-control"] == "no-store"
    finally:
        app.dependency_overrides[quick_test_context.get_current_user] = override


def test_retention_preview_and_apply_are_scoped_and_keep_recent_data(db):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)
    old = now - timedelta(days=100)
    for tenant, timestamp in [("tenant-a", old), ("tenant-a", now), ("tenant-b", old)]:
        db.add(Interaction(tenant_id=tenant, question="Pergunta pessoal", answer="Resposta", asked_at=timestamp))
        question = UnansweredQuestion(
            tenant_id=tenant, canonical_question="Pergunta pessoal", first_asked=timestamp,
            last_asked=now, converted=True,
        )
        db.add(question)
        db.flush()
        db.add(UnansweredSuppression(
            tenant_id=tenant, fingerprint="f" * 64, question_id=question.id,
            created_at=now,
        ))
    db.flush()
    expected = {"suppressions": 1, "unanswered": 1, "interactions": 1}
    assert purge_chat_data(db, tenant_id="tenant-a", cutoff=cutoff) == expected
    assert db.query(Interaction).count() == 3
    assert purge_chat_data(db, tenant_id="tenant-a", cutoff=cutoff, apply=True) == expected
    assert db.query(Interaction).count() == 2
    assert db.query(UnansweredQuestion).count() == 2
    assert db.query(UnansweredSuppression).count() == 2
    assert db.query(Interaction).filter(Interaction.tenant_id == "tenant-b").count() == 1
    assert purge_chat_data(db, tenant_id="tenant-a", cutoff=cutoff, apply=True) == dict.fromkeys(expected, 0)


def test_retention_rejects_empty_tenant(db):
    with pytest.raises(ValueError):
        purge_chat_data(db, tenant_id=" ", cutoff=datetime.now(timezone.utc), apply=True)
