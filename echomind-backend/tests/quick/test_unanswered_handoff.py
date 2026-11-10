import json
from datetime import timedelta
from unittest.mock import patch

import pytest

from app.database import Config, Interaction, UnansweredQuestion, UnansweredSuppression, utc_now
from app.unanswered_handoff import HANDOFF_TTL
from app.unanswered_triage import question_fingerprint


@pytest.fixture
def db(quick_test_context):
    # Each request must really commit/rollback without rolling back setup data.
    # SQLite's legacy driver otherwise releases savepoints outside a real BEGIN.
    connection = quick_test_context.engine.connect()
    transaction = connection.begin()
    connection.exec_driver_sql("BEGIN")
    session = quick_test_context.session_factory(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def events(response):
    return [(frame.splitlines()[0][7:], json.loads(frame.splitlines()[1][6:]))
            for frame in response.text.strip().split("\n\n")]


@pytest.fixture
def public_chat(client, privacy_config_data, fake_rag_engine):
    config = client.put("/config", json=privacy_config_data).json()
    fake_rag_engine.has_context = False
    return f"/public/{config['public_slug']}"


def offer(client, path, question="Qual o prazo de matrícula? Meu CPF é 123.456.789-00."):
    response = client.post(f"{path}/chat", json={"message": question}, headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = events(response)
    assert frames[-1][0] == "done"
    return frames[-1][1]["unanswered_token"]


def test_public_question_waits_for_confirmation_and_confirm_is_idempotent(client, db, public_chat):
    token = offer(client, public_chat)
    assert len(token) == 43
    assert db.query(UnansweredQuestion).count() == 0
    row = db.query(Interaction).one()
    assert row.question.endswith("CPF é [DADO].")
    assert row.unanswered_token_hash != token and row.unanswered_submitted_at is None
    for _ in range(2):
        assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    db.expire_all()
    submitted = db.query(UnansweredQuestion).one()
    assert submitted.canonical_question == row.question and submitted.count == 1
    assert row.unanswered_submitted_at is not None


def test_other_institution_and_invented_token_cannot_submit(client, db, public_chat, privacy_config_data):
    token = offer(client, public_chat)
    db.add(Config(tenant_id="other", public_slug="other", company_name="Other", **privacy_config_data))
    db.commit()
    assert client.post("/public/other/unanswered", json={"token": token}).status_code == 400
    assert client.post(f"{public_chat}/unanswered", json={"token": "x" * 43}).status_code == 400
    assert db.query(UnansweredQuestion).count() == 0


@pytest.mark.parametrize("body", [{"token": "short"}, {"token": "x" * 44}, {"token": "?" * 43}, {"token": "x" * 43, "question": "Replacement"}])
def test_submit_accepts_only_the_opaque_token(client, public_chat, body):
    assert client.post(f"{public_chat}/unanswered", json=body).status_code == 422


def test_expired_deleted_offers_are_rejected_but_cleanup_does_not_block_submission(client, db, public_chat):
    token = offer(client, public_chat)
    row = db.query(Interaction).one()
    row.asked_at = utc_now() - HANDOFF_TTL - timedelta(seconds=1)
    db.commit()
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 400
    db.delete(row); db.commit()
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 400
    token = offer(client, public_chat)
    client.put("/config", json={"privacy_email": None})
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    assert db.query(UnansweredQuestion).count() == 1


def test_public_chat_and_confirmation_work_without_privacy_configuration(client, db, fake_rag_engine):
    config = client.get("/config").json()
    assert config["privacy_ready"] is False
    assert config["chat_retention_enabled"] is True
    fake_rag_engine.has_context = False
    path = f"/public/{config['public_slug']}"
    token = offer(client, path)
    assert db.query(UnansweredQuestion).count() == 0
    assert client.post(f"{path}/unanswered", json={"token": token}).status_code == 204
    assert db.query(UnansweredQuestion).one().count == 1


def test_failures_roll_back_receipt_and_queue_and_allow_retry(client, db, public_chat, caplog):
    token = offer(client, public_chat)
    from app.rag_engine import register_unanswered_question

    def fail_after_write(question, tenant, session):
        register_unanswered_question(question, tenant, session)
        raise RuntimeError("synthetic failure")

    with patch("app.rag_engine.register_unanswered_question", side_effect=fail_after_write):
        response = client.post(f"{public_chat}/unanswered", json={"token": token})
    assert response.status_code == 503
    assert token not in response.text + caplog.text
    assert db.query(UnansweredQuestion).count() == 0
    assert db.query(Interaction).one().unanswered_submitted_at is None
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    assert db.query(UnansweredQuestion).one().count == 1


def test_answered_and_faq_cache_do_not_offer_handoff(client, db, public_chat, fake_rag_engine):
    fake_rag_engine.has_context = True
    assert offer(client, public_chat) is None
    with patch("app.crud.find_cached_faq_answer", return_value=("faq", "Resposta pública")), patch("app.crud.increment_faq_consult"):
        assert offer(client, public_chat) is None
    assert all(row.unanswered_token_hash is None for row in db.query(Interaction).all())
    assert db.query(UnansweredQuestion).count() == 0


@pytest.mark.parametrize("partial", [False, True])
def test_generation_failure_does_not_offer_or_enqueue(client, db, public_chat, fake_rag_engine, partial):
    async def broken(question):
        fake_rag_engine.last_had_docs = False
        if partial:
            yield "Resposta parcial"
        raise RuntimeError("synthetic failure")

    with patch.object(fake_rag_engine, "astream_chat", side_effect=broken):
        response = client.post(f"{public_chat}/chat", json={"message": "Onde fica a secretaria?"}, headers={"Accept": "text/event-stream"})
    assert events(response)[-1][0] == "error"
    assert db.query(Interaction).one().unanswered_token_hash is None
    assert db.query(UnansweredQuestion).count() == 0


def test_no_offer_is_issued_if_history_cannot_be_saved(client, public_chat):
    with patch("app.crud.save_interaction", return_value=None):
        assert offer(client, public_chat) is None


def test_plain_text_clients_do_not_enqueue_without_confirmation(client, db, public_chat):
    response = client.post(f"{public_chat}/chat", json={"message": "Onde fica a secretaria?"})
    assert response.headers["content-type"].startswith("text/plain")
    assert "Não tenho informações" in response.text
    assert db.query(UnansweredQuestion).count() == 0
    assert db.query(Interaction).one().unanswered_token_hash is None


def test_confirmation_preserves_existing_triage_suppression_and_grouping(client, db, public_chat):
    question = "Onde fica a secretaria?"
    for _ in range(2):
        token = offer(client, public_chat, question)
        assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    assert db.query(UnansweredQuestion).one().count == 2
    db.add(UnansweredSuppression(tenant_id="test-admin", question_id="ignored", fingerprint=question_fingerprint(question)))
    db.commit()
    token = offer(client, public_chat, question)
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    assert db.query(UnansweredQuestion).one().count == 2


def test_confirmation_has_chat_rate_limit(client, public_chat):
    from app.rate_limit import RATE_LIMIT_CONFIG, rate_limiter
    token = offer(client, public_chat)
    rate_limiter.clear()
    for _ in range(RATE_LIMIT_CONFIG.chat.max_requests):
        assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 204
    assert client.post(f"{public_chat}/unanswered", json={"token": token}).status_code == 429
