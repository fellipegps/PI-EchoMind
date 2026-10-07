"""Triagem da fila sem dependência de LLM ou de banco externo."""

import json
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from app import crud, rag_engine
from app.database import UnansweredQuestion, UnansweredSuppression
from app.unanswered_triage import (
    classify_group_v1,
    classify_question_v1,
    question_fingerprint,
)


@pytest.mark.parametrize(
    ("question", "status"),
    [
        ("Onde vejo minhas notas?", "pending"),
        ("Que porra é o prazo de matrícula?", "review"),
        ("vai se danar, quero saber de descontos da base aerea", "review"),
        ("Seu babaca, como consigo bolsa?", "review"),
        ("Vai se lascar, qual é o prazo de inscrição?", "review"),
        ("Cala a boca, quero saber da matrícula", "review"),
        ("Vtnc, quando abre a inscrição?", "review"),
        ("P0RRA, onde vejo minhas notas?", "review"),
        ("P*RR@, onde vejo minhas notas?", "review"),
        ("Car@lho, como peço desconto?", "review"),
        ("Qual a previsão do tempo?", "review"),
        ("Matrícula", "review"),
        ("Como funciona o desconto da base aérea?", "pending"),
        ("Onde encontro o cupom de inscrição?", "pending"),
        ("PORRA!!!", "discard"),
        ("vai se foder", "discard"),
        ("vai se danar", "discard"),
        ("vai tomar no cu", "discard"),
        ("vai se lascar", "discard"),
        ("cala a boca", "discard"),
        ("seu arrombado", "discard"),
        ("vtnc", "discard"),
        ("oi", "discard"),
        ("https://spam.example", "discard"),
        ("aaaaaa", "discard"),
        ("🙂🙂🙂", "discard"),
    ],
)
def test_classification_is_conservative(question, status):
    assert classify_question_v1(question).status == status


def test_fingerprint_ignores_case_accents_and_punctuation():
    assert question_fingerprint("Onde é a matrícula?") == question_fingerprint(
        "ONDE E A MATRICULA!!!"
    )


def test_legacy_group_with_abusive_variation_requires_review():
    decision = classify_group_v1([
        "Onde vejo minhas notas?",
        "Onde vejo minhas notas, porra?",
    ])
    assert decision.status == "review"
    assert decision.reason == "abusive_language"


def test_registration_separates_actionable_review_and_noise(db, monkeypatch):
    monkeypatch.setattr(rag_engine, "SessionLocal", sessionmaker(bind=db.connection()))

    rag_engine._register_unanswered_standalone("Onde vejo minhas notas?", "test-admin")
    rag_engine._register_unanswered_standalone("Que porra é o prazo de matrícula?", "test-admin")
    rag_engine._register_unanswered_standalone(
        "vai se danar, quero saber de descontos da base aerea", "test-admin"
    )
    rag_engine._register_unanswered_standalone("PORRA!!!", "test-admin")

    assert [row["canonical_question"] for row in crud.get_unanswered_questions(db, "test-admin")] == [
        "Onde vejo minhas notas?"
    ]
    review = crud.get_unanswered_questions(db, "test-admin", "review")
    assert {row["canonical_question"] for row in review} == {
        "vai se danar, quero saber de descontos da base aerea",
        "Que porra é o prazo de matrícula?",
    }
    assert all(row["triage_reason"] == "abusive_language" for row in review)
    assert db.query(UnansweredQuestion).filter_by(tenant_id="test-admin").count() == 3
    assert crud.get_dashboard_stats(db, "test-admin")["unanswered_questions"] == 1


def test_exact_question_groups_even_after_more_than_100_newer_rows(db, monkeypatch):
    question = "Onde vejo meu histórico acadêmico?"
    old_row = UnansweredQuestion(
        tenant_id="test-admin",
        canonical_question=question,
        fingerprint=question_fingerprint(question),
        last_asked=datetime(2000, 1, 1),
    )
    db.add(old_row)
    for index in range(101):
        db.add(UnansweredQuestion(
            tenant_id="test-admin",
            canonical_question=f"Pergunta diferente número {index}?",
        ))
    db.flush()
    monkeypatch.setattr(rag_engine, "SessionLocal", sessionmaker(bind=db.connection()))

    rag_engine._register_unanswered_standalone(question, "test-admin")

    db.expire_all()
    assert db.query(UnansweredQuestion).filter_by(tenant_id="test-admin").count() == 102
    assert old_row.count == 2


def test_ignore_suppresses_known_variants_only_for_own_tenant(db, client, monkeypatch):
    monkeypatch.setattr(rag_engine, "SessionLocal", sessionmaker(bind=db.connection()))
    original = "Onde fica a secretaria?"
    variant = "Onde fica a secretaria"
    rag_engine._register_unanswered_standalone(original, "test-admin")
    rag_engine._register_unanswered_standalone(variant, "test-admin")
    row = db.query(UnansweredQuestion).filter_by(tenant_id="test-admin").one()
    assert row.count == 2
    row.similar_questions = json.dumps(["Onde fica a secretaria central?"])
    db.flush()

    assert client.post(f"/unanswered/{row.id}/ignore").status_code == 204
    assert client.get("/unanswered").json() == []
    assert len(client.get("/unanswered?status=ignored").json()) == 1
    assert db.query(UnansweredSuppression).filter_by(tenant_id="test-admin").count() == 2

    rag_engine._register_unanswered_standalone("ONDE FICA A SECRETARIA!!!", "test-admin")
    rag_engine._register_unanswered_standalone("Onde fica a secretaria central?", "test-admin")
    assert db.query(UnansweredQuestion).filter_by(tenant_id="test-admin").count() == 1

    rag_engine._register_unanswered_standalone(original, "other-tenant")
    assert len(crud.get_unanswered_questions(db, "other-tenant")) == 1
    other_row = db.query(UnansweredQuestion).filter_by(tenant_id="other-tenant").one()
    assert client.post(f"/unanswered/{other_row.id}/ignore").status_code == 404
    assert client.post(f"/unanswered/{other_row.id}/restore").status_code == 404

    assert client.post(f"/unanswered/{row.id}/restore").status_code == 204
    assert db.query(UnansweredSuppression).filter_by(tenant_id="test-admin").count() == 0
    assert len(client.get("/unanswered").json()) == 1
    rag_engine._register_unanswered_standalone(original, "test-admin")
    db.expire_all()
    assert crud.get_unanswered_questions(db, "test-admin")[0]["count"] == 3


def test_review_requires_approval_before_conversion(db, client, monkeypatch):
    row = UnansweredQuestion(
        tenant_id="test-admin",
        canonical_question="Que porra é o prazo de matrícula?",
        triage_status="review",
        triage_reason="abusive_language",
        fingerprint=question_fingerprint("Que porra é o prazo de matrícula?"),
    )
    db.add(row)
    db.flush()

    assert client.get("/unanswered").json() == []
    assert len(client.get("/unanswered?status=review").json()) == 1
    assert client.post(
        f"/unanswered/{row.id}/convert",
        json={"answer": "A matrícula começa em março."},
    ).status_code == 404
    assert client.post(f"/unanswered/{row.id}/approve").status_code == 204
    pending = client.get("/unanswered").json()
    assert len(pending) == 1
    assert pending[0]["triage_reason"] == "approved_by_admin"

    monkeypatch.setattr(rag_engine, "SessionLocal", sessionmaker(bind=db.connection()))
    rag_engine._register_unanswered_standalone(row.canonical_question, "test-admin")
    db.expire_all()
    assert len(crud.get_unanswered_questions(db, "test-admin")) == 1
    assert crud.get_unanswered_questions(db, "test-admin")[0]["count"] == 2


def test_unanswered_metric_is_emitted_before_triage(client, fake_rag_engine):
    fake_rag_engine.has_context = False
    with patch("app.main.emit_event") as emit, patch("app.main._register_unanswered_standalone"):
        response = client.post(
            "/chat", json={"message": "PORRA!!!", "tenant_id": "test-admin"}
        )

    assert response.status_code == 200
    assert any(
        call.kwargs.get("event") == "rag.unanswered"
        and call.kwargs.get("stage") == "detected"
        for call in emit.call_args_list
    )
