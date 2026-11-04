from unittest.mock import patch

import pytest

from app.chat_sanitization import sanitize_public_question
from app.database import Interaction


@pytest.mark.parametrize("identifier", [
    "123.456.789-00", "12345678900", "01234567890",
    "12.345.678/0001-00", "12345678000100",
    "aluno.teste+curso@example.test", "(62) 99999-0000", "62 3333-0000",
    "+55 (62) 99999-0000", "5562999990000", "6233330000",
    "１２３．４５６．７８９－００", "alu\u200bno@example.test", "123\x0045678900",
])
def test_common_identifiers_are_removed(identifier):
    assert sanitize_public_question(f"Onde fica a secretaria? Meu contato: {identifier}.") == (
        "Onde fica a secretaria? Meu contato: [DADO]."
    )


def test_minimizes_multiple_identifiers_and_is_idempotent():
    question = "Meu CPF é 123.456.789-00, e-mail aluno@example.test e telefone (62) 99999-0000. Onde me matriculo?"
    minimized = sanitize_public_question(question)
    assert minimized == "Meu CPF é [DADO], e-mail [DADO] e telefone [DADO]. Onde me matriculo?"
    assert sanitize_public_question(minimized) == minimized


def test_preserves_general_question_dates_accents_and_course_codes():
    question = "  Qual\t o horário\nda matrícula em 2026-10-27, curso 1234, sala B-12?  "
    assert sanitize_public_question(question) == "Qual o horário da matrícula em 2026-10-27, curso 1234, sala B-12?"


@pytest.mark.parametrize("question", ["123.456.789-00", "aluno@example.test", "\u200b\x00", " ! ", "(62) 99999-0000, aluno@example.test"])
def test_rejects_questions_with_no_remaining_content(question):
    with pytest.raises(ValueError, match="dúvida geral"):
        sanitize_public_question(question)


def test_enforces_size_before_and_after_unicode_normalization():
    assert len(sanitize_public_question("a" * 2000)) == 2000
    for question in ("a" * 2001, "\ufb03" * 1000, ("\ufb03" * 600) + (" aluno@example.test" * 11)):
        with pytest.raises(ValueError, match="2000 caracteres"):
            sanitize_public_question(question)


def test_redaction_is_not_general_anonymization_or_html_encoding():
    # Free text requires the existing notice and human review; React/Markdown
    # rendering and parameterized database queries remain separate defenses.
    question = "Meu nome é Pessoa Sintética. <b>Onde fica o campus?</b>"
    assert sanitize_public_question(question) == question


def test_public_chat_minimizes_before_cache_rag_and_history(client, db, fake_rag_engine, privacy_config_data):
    config = client.put("/config", json=privacy_config_data).json()
    question = "Meu CPF 123.456.789-00 e e-mail aluno@example.test. Onde fica o campus?"
    minimized = "Meu CPF [DADO] e e-mail [DADO]. Onde fica o campus?"
    with (
        patch("app.crud.find_cached_faq_answer", return_value=None) as lookup,
        patch.object(fake_rag_engine, "astream_chat", wraps=fake_rag_engine.astream_chat) as generate,
    ):
        response = client.post(f"/public/{config['public_slug']}/chat", json={"message": question})
    assert response.status_code == 200
    assert "123.456.789-00" not in response.text and "aluno@example.test" not in response.text
    lookup.assert_called_once_with(minimized, tenant_id="test-admin")
    generate.assert_called_once_with(minimized)
    row = db.query(Interaction).filter_by(tenant_id="test-admin").one()
    assert row.question == minimized
    assert "123.456.789-00" not in row.answer and "aluno@example.test" not in row.answer


def test_public_faq_cache_is_minimized_and_unanswered_is_not_automatic(client, db, fake_rag_engine, privacy_config_data):
    config = client.put("/config", json=privacy_config_data).json()
    url = f"/public/{config['public_slug']}/chat"
    question = "Onde fica a secretaria? (62) 99999-0000"
    minimized = "Onde fica a secretaria? [DADO]"
    with (
        patch("app.crud.find_cached_faq_answer", return_value=("synthetic-faq", "Resposta pública")) as lookup,
        patch("app.crud.increment_faq_consult"),
        patch("app.main.get_rag_engine") as rag,
    ):
        assert client.post(url, json={"message": question}).text == "Resposta pública"
    lookup.assert_called_once_with(minimized, tenant_id="test-admin")
    rag.assert_not_called()
    fake_rag_engine.has_context = False
    with patch("app.main._register_unanswered_standalone") as register:
        assert client.post(url, json={"message": question}).status_code == 200
    register.assert_not_called()
    assert all(row.question == minimized for row in db.query(Interaction).all())


def test_rejected_public_input_has_no_processing_persistence_or_sensitive_logs(client, db, privacy_config_data, caplog):
    config = client.put("/config", json=privacy_config_data).json()
    with patch("app.crud.find_cached_faq_answer") as lookup, patch("app.main.get_rag_engine") as rag:
        response = client.post(f"/public/{config['public_slug']}/chat", json={"message": "123.456.789-00"})
    assert response.status_code == 400
    assert "123.456.789-00" not in response.text + caplog.text
    lookup.assert_not_called()
    rag.assert_not_called()
    assert db.query(Interaction).count() == 0


def test_authenticated_legacy_chat_keeps_existing_contract(client, db):
    question = "Contato sintético: aluno@example.test"
    assert client.post("/chat", json={"message": question, "tenant_id": "test-admin"}).status_code == 200
    assert db.query(Interaction).one().question == question
