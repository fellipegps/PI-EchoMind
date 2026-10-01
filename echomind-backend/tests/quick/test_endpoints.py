"""
tests/test_events.py – CRUD de Eventos
tests/test_config.py – Configurações
tests/test_chat.py   – Endpoint de chat com streaming
tests/test_unanswered.py – Perguntas não respondidas

(Todos no mesmo arquivo para organização compacta)
"""

import pytest
from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateEvent:
    def test_create_event_success(self, client: TestClient, sample_event_data: dict):
        resp = client.post("/events", json=sample_event_data)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == sample_event_data["title"]
        assert data["event_date"] == sample_event_data["event_date"]
        assert data["event_end_date"] == sample_event_data["event_end_date"]
        assert data["event_type"] == sample_event_data["event_type"]
        assert data["course"] == sample_event_data["course"]
        assert data["location"] == sample_event_data["location"]
        assert data["image_url"] == sample_event_data["image_url"]
        assert data["link_url"] == sample_event_data["link_url"]
        assert "published" not in data
        assert "id" in data

    def test_create_event_defaults_end_to_start(self, client: TestClient, sample_event_data: dict):
        payload = {**sample_event_data}
        payload.pop("event_end_date")
        resp = client.post("/events", json=payload)
        assert resp.status_code == 201
        assert resp.json()["event_end_date"] == payload["event_date"]

    def test_create_event_invalid_date(self, client: TestClient, sample_event_data: dict):
        resp = client.post("/events", json={**sample_event_data, "event_date": "20-08-2025"})
        assert resp.status_code == 422

    @pytest.mark.parametrize("field", ["event_date", "event_end_date"])
    def test_create_event_rejects_nonexistent_date(
        self, client: TestClient, sample_event_data: dict, field: str
    ):
        resp = client.post("/events", json={**sample_event_data, field: "2026-02-30"})
        assert resp.status_code == 422

    def test_create_event_rejects_end_before_start(self, client: TestClient, sample_event_data: dict):
        resp = client.post(
            "/events",
            json={**sample_event_data, "event_date": "2099-08-20", "event_end_date": "2099-08-19"},
        )
        assert resp.status_code == 422

    def test_create_event_rejects_end_in_past(self, client: TestClient, sample_event_data: dict):
        resp = client.post(
            "/events",
            json={**sample_event_data, "event_date": "2000-01-01", "event_end_date": "2000-01-02"},
        )
        assert resp.status_code == 422

    def test_create_event_invalid_type(self, client: TestClient, sample_event_data: dict):
        resp = client.post("/events", json={**sample_event_data, "event_type": "tipo_invalido"})
        assert resp.status_code == 422

    def test_create_event_no_description(self, client: TestClient, sample_event_data: dict):
        payload = {**sample_event_data}
        payload.pop("description")
        resp = client.post("/events", json=payload)
        assert resp.status_code == 201
        assert resp.json()["description"] is None

    @pytest.mark.parametrize("link_url", ["javascript:alert(1)", "ftp://example.com/file"])
    def test_create_event_rejects_invalid_link_url(
        self, client: TestClient, sample_event_data: dict, link_url: str
    ):
        resp = client.post("/events", json={**sample_event_data, "link_url": link_url})
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "image_url",
        [
            "http://example.com/capa.jpg",
            "javascript:alert(1)",
            "data:image/png;base64,abc",
            "https://usuario:senha@example.com/capa.jpg",
        ],
    )
    def test_create_event_rejects_invalid_image_url(
        self, client: TestClient, sample_event_data: dict, image_url: str
    ):
        resp = client.post("/events", json={**sample_event_data, "image_url": image_url})
        assert resp.status_code == 422

    def test_create_event_normalizes_empty_urls(self, client: TestClient, sample_event_data: dict):
        resp = client.post(
            "/events",
            json={**sample_event_data, "image_url": "", "link_url": "   "},
        )
        assert resp.status_code == 201
        assert resp.json()["image_url"] is None
        assert resp.json()["link_url"] is None


class TestListEvents:
    def test_list_events_empty(self, client: TestClient):
        resp = client.get("/events")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_events_returns_all(self, client: TestClient, sample_event_data: dict):
        client.post("/events", json=sample_event_data)
        client.post("/events", json={**sample_event_data, "title": "Outro Evento Acadêmico"})
        resp = client.get("/events")
        assert len(resp.json()) == 2


class TestEventCourses:
    def test_lists_general_and_courses_created_with_events(
        self,
        client: TestClient,
        sample_event_data: dict,
    ):
        client.post("/events", json=sample_event_data)

        response = client.get("/events/courses")

        assert response.status_code == 200
        assert [course["name"] for course in response.json()] == [
            "Engenharia Civil",
            "Geral",
        ]

    def test_creates_a_new_course_and_reuses_case_insensitive_duplicate(
        self,
        client: TestClient,
    ):
        created = client.post("/events/courses", json={"name": "Medicina"})
        duplicate = client.post("/events/courses", json={"name": " medicina "})

        assert created.status_code == 201
        assert duplicate.status_code == 201
        assert duplicate.json() == created.json()

    def test_rejects_blank_course(self, client: TestClient):
        response = client.post("/events/courses", json={"name": "   "})
        assert response.status_code == 422


class TestUpdateEvent:
    def test_update_event(self, client: TestClient, sample_event_data: dict):
        created = client.post("/events", json=sample_event_data).json()
        resp = client.put(f"/events/{created['id']}", json={"title": "Novo Título do Evento"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Novo Título do Evento"

    def test_update_event_not_found(self, client: TestClient):
        resp = client.put("/events/nao-existe", json={"title": "Título Qualquer"})
        assert resp.status_code == 404

    def test_update_event_clears_image_url(self, client: TestClient, sample_event_data: dict):
        created = client.post("/events", json=sample_event_data).json()
        response = client.put(f"/events/{created['id']}", json={"image_url": None})
        assert response.status_code == 200
        assert response.json()["image_url"] is None

    def test_update_event_validates_merged_period(self, client: TestClient, sample_event_data: dict):
        created = client.post("/events", json=sample_event_data).json()
        response = client.put(f"/events/{created['id']}", json={"event_date": "2099-08-23"})
        assert response.status_code == 422

    def test_update_event_rejects_invalid_type(
        self,
        client: TestClient,
        sample_event_data: dict,
    ):
        created = client.post("/events", json=sample_event_data).json()

        response = client.put(
            f"/events/{created['id']}",
            json={"event_type": "tipo_invalido"},
        )

        assert response.status_code == 422


class TestDeleteEvent:
    def test_delete_event(self, client: TestClient, sample_event_data: dict):
        created = client.post("/events", json=sample_event_data).json()
        resp = client.delete(f"/events/{created['id']}")
        assert resp.status_code == 204

    def test_delete_event_not_found(self, client: TestClient):
        resp = client.delete("/events/nao-existe")
        assert resp.status_code == 404

    def test_event_mutations_do_not_touch_rag(
        self,
        client: TestClient,
        sample_event_data: dict,
        fake_rag_engine,
    ):
        created = client.post("/events", json=sample_event_data).json()
        assert client.put(f"/events/{created['id']}", json={"title": "Evento atualizado"}).status_code == 200
        assert client.delete(f"/events/{created['id']}").status_code == 204
        assert fake_rag_engine.indexed_faqs == []
        assert fake_rag_engine.deleted == []


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_get_config_not_found(self, client: TestClient):
        resp = client.get("/config")
        assert resp.status_code == 200

    def test_upsert_creates_config(self, client: TestClient, sample_config_data: dict):
        resp = client.put("/config", json=sample_config_data)
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == sample_config_data["company_name"]
        assert data["website"] == sample_config_data["website"]

    def test_upsert_updates_config(self, client: TestClient, sample_config_data: dict):
        client.put("/config", json=sample_config_data)
        resp = client.put("/config", json={"company_name": "Nova Instituição"})
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "Nova Instituição"

    def test_get_config_after_create(self, client: TestClient, sample_config_data: dict):
        client.put("/config", json=sample_config_data)
        resp = client.get("/config")
        assert resp.status_code == 200
        assert resp.json()["company_name"] == sample_config_data["company_name"]

    def test_partial_update(self, client: TestClient, sample_config_data: dict):
        client.put("/config", json=sample_config_data)
        resp = client.put("/config", json={"phone": "(11) 99999-9999"})
        assert resp.status_code == 200
        # Nome deve permanecer
        assert resp.json()["company_name"] == sample_config_data["company_name"]
        assert resp.json()["phone"] == "(11) 99999-9999"


# ══════════════════════════════════════════════════════════════════════════════
#  CHAT (Streaming)
# ══════════════════════════════════════════════════════════════════════════════

class TestChat:
    def test_chat_returns_streaming_response(self, client: TestClient):
        resp = client.post("/chat", json={"message": "Como faço minha matrícula?", "tenant_id": "test-admin"})
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        assert len(resp.text) > 0

    def test_chat_empty_message_rejected(self, client: TestClient):
        resp = client.post("/chat", json={"message": "", "tenant_id": "test-admin"})
        assert resp.status_code == 422

    def test_chat_whitespace_message_rejected(self, client: TestClient):
        resp = client.post("/chat", json={"message": "   ", "tenant_id": "test-admin"})
        assert resp.status_code == 400

    def test_chat_message_too_long(self, client: TestClient):
        resp = client.post("/chat", json={"message": "x" * 2001, "tenant_id": "test-admin"})
        assert resp.status_code == 422

    def test_chat_missing_message_field(self, client: TestClient):
        resp = client.post("/chat", json={})
        assert resp.status_code == 422

    def test_chat_response_contains_text(self, client: TestClient):
        resp = client.post("/chat", json={"message": "Onde fica a secretaria?", "tenant_id": "test-admin"})
        assert resp.status_code == 200
        assert resp.text.strip() != ""


# ══════════════════════════════════════════════════════════════════════════════
#  UNANSWERED QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════

class TestUnansweredQuestions:
    def test_list_unanswered_empty(self, client: TestClient):
        resp = client.get("/unanswered")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_convert_to_faq(self, client: TestClient, db):
        """
        Simula conversão de pergunta não respondida em FAQ.
        Primeiro cria manualmente uma UnansweredQuestion no banco via fixture.
        """
        from app.database import UnansweredQuestion
        import uuid

        # Usa a mesma sessão injetada no endpoint para comprovar a conversão.
        uq = UnansweredQuestion(
            id=str(uuid.uuid4()),
            tenant_id="test-admin",
            canonical_question="Onde fica o bloco de odontologia?",
            similar_questions='["como chego na odonto"]',
            count=5,
        )
        db.add(uq)
        db.flush()

        resp = client.post(
            f"/unanswered/{uq.id}/convert",
            json={"answer": "O bloco de odontologia fica no Bloco C, 2º andar."},
        )
        assert resp.status_code == 201
        assert resp.json()["question"] == uq.canonical_question
        assert resp.json()["answer"] == "O bloco de odontologia fica no Bloco C, 2º andar."
        db.refresh(uq)
        assert uq.converted is True

    def test_convert_not_found(self, client: TestClient):
        resp = client.post(
            "/unanswered/id-inexistente/convert",
            json={"answer": "Resposta aqui para teste de não encontrado."},
        )
        assert resp.status_code == 404

    def test_convert_empty_answer(self, client: TestClient):
        resp = client.post(
            "/unanswered/qualquer-id/convert",
            json={"answer": ""},
        )
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_returns_expected_shape(self, client: TestClient):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_questions" in data
        assert "unanswered_questions" in data
        assert "avg_response_time" in data
        assert "daily_interactions" in data
        assert "top_faqs" in data
        assert isinstance(data["daily_interactions"], list)
        assert len(data["daily_interactions"]) == 7

    def test_dashboard_daily_has_date_and_count(self, client: TestClient):
        resp = client.get("/dashboard")
        for item in resp.json()["daily_interactions"]:
            assert "date" in item
            assert "count" in item
            assert isinstance(item["count"], int)


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH
# ══════════════════════════════════════════════════════════════════════════════

class TestHealth:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

