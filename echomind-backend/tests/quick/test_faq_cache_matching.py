from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app import crud
from app.schemas import FaqCreate, FaqUpdate


MATCH_DATASET = (
    ("Como recuperar a senha do portal?", "Como recuperar a senha do portal?", True),
    ("Onde fica a secretaria acadêmica?", "ONDE FICA A SECRETARIA ACADÊMICA?", True),
    ("Como faço minha matrícula?", "Como faco minha matricula?", True),
    ("Qual é o prazo de matrícula?", "Qual é o prazo de matrícula.", True),
    ("Como emitir a segunda via?", "Como   emitir a segunda via?", True),
    ("O Wi-Fi está disponível?", "  o wi fi esta disponivel!!! ", True),
    ("Senha", "Como recuperar minha senha?", False),
    ("Como recuperar senha do portal?", "Como recuperar senha", False),
    ("Qual é o prazo de matrícula", "Qual é o prazo de matrícula para transferência?", False),
    ("Matrícula", "Qual é o calendário de matrícula?", False),
    ("Onde fica a secretaria", "Onde fica a secretaria de pós-graduação?", False),
    ("Como emitir boleto?", "Quando vence a mensalidade?", False),
)


def _legacy_substring_match(question: str, faq_question: str) -> bool:
    normalized = question.strip().lower()
    faq_normalized = faq_question.strip().lower()
    return bool(
        len(normalized) >= 4
        and (
            normalized == faq_normalized
            or normalized in faq_normalized
            or faq_normalized in normalized
        )
    )


@pytest.mark.parametrize(
    ("faq_question", "question", "expected"),
    MATCH_DATASET,
)
def test_safe_match_dataset(faq_question: str, question: str, expected: bool):
    matched = (
        crud.faq_cache_match_score(question, faq_question)
        >= crud.FAQ_CACHE_MATCH_THRESHOLD
    )
    assert matched is expected


def test_safe_strategy_improves_hits_and_removes_known_false_positives():
    positives = sum(expected for _, _, expected in MATCH_DATASET)
    negatives = len(MATCH_DATASET) - positives

    legacy_true_positives = sum(
        expected and _legacy_substring_match(question, faq_question)
        for faq_question, question, expected in MATCH_DATASET
    )
    legacy_false_positives = sum(
        not expected and _legacy_substring_match(question, faq_question)
        for faq_question, question, expected in MATCH_DATASET
    )
    safe_true_positives = sum(
        expected
        and crud.faq_cache_match_score(question, faq_question)
        >= crud.FAQ_CACHE_MATCH_THRESHOLD
        for faq_question, question, expected in MATCH_DATASET
    )
    safe_false_positives = sum(
        not expected
        and crud.faq_cache_match_score(question, faq_question)
        >= crud.FAQ_CACHE_MATCH_THRESHOLD
        for faq_question, question, expected in MATCH_DATASET
    )

    assert (positives, negatives) == (6, 6)
    assert (legacy_true_positives, legacy_false_positives) == (2, 5)
    assert (safe_true_positives, safe_false_positives) == (6, 0)


def test_find_cached_answer_is_tenant_scoped(monkeypatch: pytest.MonkeyPatch):
    answers_by_tenant = {
        "tenant-a": (("faq-a", "Como recuperar a senha?", "Resposta A"),),
        "tenant-b": (("faq-b", "Como recuperar a senha?", "Resposta B"),),
        "tenant-empty": (),
    }
    observed_tenants: list[str] = []

    def cached_answers(tenant_id: str):
        observed_tenants.append(tenant_id)
        return answers_by_tenant[tenant_id]

    monkeypatch.setattr(crud, "get_cached_faq_answers", cached_answers)

    assert crud.find_cached_faq_answer("Como recuperar a senha?", "tenant-a") == (
        "faq-a",
        "Resposta A",
    )
    assert crud.find_cached_faq_answer("Como recuperar a senha?", "tenant-b") == (
        "faq-b",
        "Resposta B",
    )
    assert crud.find_cached_faq_answer("Como recuperar a senha?", "tenant-empty") is None
    assert observed_tenants == ["tenant-a", "tenant-b", "tenant-empty"]


def test_ambiguous_normalized_matches_fall_back_instead_of_choosing_an_answer(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        crud,
        "get_cached_faq_answers",
        lambda tenant_id: (
            ("faq-1", "Como faço a matrícula?", "Resposta 1"),
            ("faq-2", "COMO FACO A MATRICULA!!!", "Resposta 2"),
        ),
    )

    assert crud.find_cached_faq_answer("Como faco a matricula?", "tenant-a") is None


def test_faq_mutations_invalidate_cached_rows(db, monkeypatch: pytest.MonkeyPatch):
    cached_answers = Mock()
    cached_answers.cache_clear = Mock()
    monkeypatch.setattr(crud, "get_cached_faq_answers", cached_answers)

    faq = crud.create_faq(
        db,
        FaqCreate(question="Como recuperar a senha?", answer="Resposta inicial."),
        tenant_id="tenant-cache",
    )
    crud.update_faq(
        db,
        faq.id,
        FaqUpdate(question="Como alterar a senha?", answer="Resposta atualizada."),
        tenant_id="tenant-cache",
    )
    crud.increment_faq_consult(db, faq.id, tenant_id="tenant-cache")
    assert crud.delete_faq(db, faq.id, tenant_id="tenant-cache") is True

    assert cached_answers.cache_clear.call_count == 4


def test_cache_miss_preserves_current_rag_fallback(
    client: TestClient,
    fake_rag_engine,
):
    question = "Pergunta lexicalmente diferente da FAQ"
    with patch("app.crud.find_cached_faq_answer", return_value=None) as matcher:
        response = client.post(
            "/chat",
            json={"message": question, "tenant_id": "test-admin"},
        )

    assert response.status_code == 200
    assert response.text == f"Resposta simulada para: {question} "
    assert fake_rag_engine.last_had_docs is True
    matcher.assert_called_once_with(question, tenant_id="test-admin")
