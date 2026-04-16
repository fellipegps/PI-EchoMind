"""
tests/test_faqs.py – Testes completos do CRUD de FAQs.
"""

import pytest
from fastapi.testclient import TestClient


class TestCreateFaq:
    def test_create_faq_success(self, client: TestClient, sample_faq_data: dict):
        resp = client.post("/faqs", json=sample_faq_data)
        assert resp.status_code == 201
        data = resp.json()
        assert data["question"] == sample_faq_data["question"]
        assert data["answer"] == sample_faq_data["answer"]
        assert data["show_on_totem"] is False
        assert "id" in data
        assert "created_at" in data

    def test_create_faq_show_on_totem(self, client: TestClient, sample_faq_data: dict):
        payload = {**sample_faq_data, "show_on_totem": True}
        resp = client.post("/faqs", json=payload)
        assert resp.status_code == 201
        assert resp.json()["show_on_totem"] is True

    def test_create_faq_question_too_short(self, client: TestClient):
        resp = client.post("/faqs", json={"question": "OK?", "answer": "Sim."})
        assert resp.status_code == 422

    def test_create_faq_missing_answer(self, client: TestClient):
        resp = client.post("/faqs", json={"question": "Uma pergunta válida aqui?"})
        assert resp.status_code == 422

    def test_create_faq_empty_body(self, client: TestClient):
        resp = client.post("/faqs", json={})
        assert resp.status_code == 422


class TestListFaqs:
    def test_list_faqs_empty(self, client: TestClient):
        resp = client.get("/faqs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_faqs_returns_all(self, client: TestClient, sample_faq_data: dict):
        client.post("/faqs", json=sample_faq_data)
        client.post("/faqs", json={**sample_faq_data, "question": "Outra pergunta válida aqui?"})
        resp = client.get("/faqs")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_totem_faqs_only_marked(self, client: TestClient, sample_faq_data: dict):
        # Cria 2 FAQs: 1 no totem, 1 fora
        client.post("/faqs", json={**sample_faq_data, "show_on_totem": True})
        client.post("/faqs", json={**sample_faq_data,
                                   "question": "Segunda pergunta completamente válida?",
                                   "show_on_totem": False})
        resp = client.get("/faqs/totem")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["show_on_totem"] is True


class TestUpdateFaq:
    def test_update_faq_success(self, client: TestClient, sample_faq_data: dict):
        created = client.post("/faqs", json=sample_faq_data).json()
        faq_id = created["id"]

        resp = client.put(f"/faqs/{faq_id}", json={"answer": "Nova resposta completa aqui."})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "Nova resposta completa aqui."
        # Campo não atualizado deve permanecer
        assert resp.json()["question"] == sample_faq_data["question"]

    def test_update_faq_not_found(self, client: TestClient):
        resp = client.put("/faqs/nao-existe-id", json={"answer": "Qualquer coisa aqui."})
        assert resp.status_code == 404


class TestToggleTotemFaq:
    def test_toggle_activates(self, client: TestClient, sample_faq_data: dict):
        created = client.post("/faqs", json=sample_faq_data).json()
        faq_id = created["id"]

        resp = client.patch(f"/faqs/{faq_id}/toggle-totem")
        assert resp.status_code == 200
        assert resp.json()["show_on_totem"] is True

    def test_toggle_deactivates(self, client: TestClient, sample_faq_data: dict):
        created = client.post("/faqs", json={**sample_faq_data, "show_on_totem": True}).json()
        faq_id = created["id"]

        resp = client.patch(f"/faqs/{faq_id}/toggle-totem")
        assert resp.status_code == 200
        assert resp.json()["show_on_totem"] is False

    def test_toggle_limit_4_faqs(self, client: TestClient, sample_faq_data: dict):
        """Não deve permitir mais de 4 FAQs ativas no totem."""
        ids = []
        for i in range(4):
            r = client.post("/faqs", json={
                **sample_faq_data,
                "question": f"Pergunta número {i+1} completamente válida?",
                "show_on_totem": True,
            })
            ids.append(r.json()["id"])

        # Quinta FAQ — ativar deve retornar 409
        fifth = client.post("/faqs", json={
            **sample_faq_data,
            "question": "Quinta pergunta tentando entrar no totem?",
            "show_on_totem": False,
        }).json()

        resp = client.patch(f"/faqs/{fifth['id']}/toggle-totem")
        assert resp.status_code == 409
        assert "Limite" in resp.json()["detail"]

    def test_toggle_not_found(self, client: TestClient):
        resp = client.patch("/faqs/id-inexistente/toggle-totem")
        assert resp.status_code == 404


class TestDeleteFaq:
    def test_delete_faq_success(self, client: TestClient, sample_faq_data: dict):
        created = client.post("/faqs", json=sample_faq_data).json()
        faq_id = created["id"]

        resp = client.delete(f"/faqs/{faq_id}")
        assert resp.status_code == 204

        # Confirma que foi removida
        resp = client.get("/faqs")
        assert all(f["id"] != faq_id for f in resp.json())

    def test_delete_faq_not_found(self, client: TestClient):
        resp = client.delete("/faqs/id-que-nao-existe")
        assert resp.status_code == 404
