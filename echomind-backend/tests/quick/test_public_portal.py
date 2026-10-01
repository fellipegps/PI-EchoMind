"""Contrato público por slug, sem exposição ou confiança no tenant interno."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.database import CompanyEvent, Config, Faq


def test_public_slug_is_valid_stable_and_distinct_between_tenants() -> None:
    slug_a = crud.build_public_slug("UniEVANGÉLICA Anápolis", "tenant-a")
    slug_b = crud.build_public_slug("UniEVANGÉLICA Anápolis", "tenant-b")

    assert slug_a.startswith("unievangelica-anapolis-")
    assert crud.is_valid_public_slug(slug_a)
    assert slug_a == crud.build_public_slug("UniEVANGÉLICA Anápolis", "tenant-a")
    assert slug_a != slug_b
    assert not crud.is_valid_public_slug("UUID COM ESPAÇOS")


def test_public_institution_resolves_slug_without_exposing_tenant(
    client: TestClient,
) -> None:
    admin_config = client.get("/config").json()

    response = client.get(f"/public/{admin_config['public_slug']}")

    assert response.status_code == 200
    assert response.json() == {
        "public_slug": admin_config["public_slug"],
        "company_name": "Empresa Teste",
        "description": (
            "Configure aqui as informacoes oficiais de Empresa Teste "
            "para orientar as respostas do agente."
        ),
        "website": None,
        "phone": None,
        "address": None,
        "business_hours": None,
    }
    assert "tenant_id" not in response.json()
    assert "id" not in response.json()


@pytest.mark.parametrize("slug", ["inexistente-1234567890abcdef", "INVALIDO"])
def test_public_institution_returns_same_safe_404_for_unknown_or_invalid_slug(
    client: TestClient,
    slug: str,
) -> None:
    response = client.get(f"/public/{slug}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Instituição não encontrada."}


def test_database_rejects_duplicate_public_slug(db: Session) -> None:
    duplicate_slug = "instituicao-1234567890abcdef"
    db.add_all(
        [
            Config(
                tenant_id="tenant-a",
                public_slug=duplicate_slug,
                company_name="Instituição A",
            ),
            Config(
                tenant_id="tenant-b",
                public_slug=duplicate_slug,
                company_name="Instituição B",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_public_faqs_are_isolated_by_resolved_tenant_and_hide_internal_metrics(
    client: TestClient,
    db: Session,
) -> None:
    config_a = Config(
        tenant_id="tenant-a",
        public_slug="instituicao-a-1234567890abcdef",
        company_name="Instituição A",
    )
    config_b = Config(
        tenant_id="tenant-b",
        public_slug="instituicao-b-1234567890abcdef",
        company_name="Instituição B",
    )
    faq_a = Faq(
        tenant_id="tenant-a",
        question="Pergunta exclusiva do tenant A?",
        answer="Resposta exclusiva do tenant A.",
        show_in_chatbot=True,
        total_consults=42,
    )
    faq_b = Faq(
        tenant_id="tenant-b",
        question="Pergunta exclusiva do tenant B?",
        answer="Resposta exclusiva do tenant B.",
        show_in_chatbot=True,
    )
    db.add_all([config_a, config_b, faq_a, faq_b])
    db.commit()

    response = client.get(f"/public/{config_a.public_slug}/faqs")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": faq_a.id,
            "question": faq_a.question,
            "answer": faq_a.answer,
        }
    ]
    assert "tenant_id" not in response.text
    assert "total_consults" not in response.text
    assert faq_b.question not in response.text


def test_public_events_are_current_ordered_and_tenant_scoped(
    client: TestClient,
    db: Session,
) -> None:
    config_a = Config(
        tenant_id="event-tenant-a",
        public_slug="eventos-a-1234567890abcdef",
        company_name="Instituição A",
    )
    config_b = Config(
        tenant_id="event-tenant-b",
        public_slug="eventos-b-1234567890abcdef",
        company_name="Instituição B",
    )
    later = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento posterior",
        event_date="2099-12-20",
        event_end_date="2099-12-21",
        event_type="palestra",
        description="Segundo na ordenação.",
        location="Auditório B",
        image_url="https://cdn.example.com/posterior.webp",
        link_url="https://example.com/posterior",
    )
    sooner = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento mais próximo",
        event_date="2099-01-10",
        event_end_date="2099-01-10",
        event_type="workshop",
        description=None,
        location="Laboratório 1",
        image_url=None,
        link_url=None,
    )
    formerly_unpublished = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento sem status",
        event_date="2099-06-01",
        event_end_date="2099-06-01",
        event_type="reuniao",
        location="Sala interna",
    )
    finished = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento encerrado",
        event_date="2000-01-01",
        event_end_date="2000-01-02",
        event_type="outro",
        location="Arquivo",
    )
    other_tenant = CompanyEvent(
        tenant_id=config_b.tenant_id,
        title="Evento do tenant B",
        event_date="2099-01-02",
        event_end_date="2099-01-03",
        event_type="outro",
        location="Outro campus",
    )
    db.add_all(
        [
            config_a,
            config_b,
            later,
            sooner,
            formerly_unpublished,
            finished,
            other_tenant,
        ]
    )
    db.commit()
    finished_title = finished.title

    response = client.get(f"/public/{config_a.public_slug}/events")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": sooner.id,
            "title": sooner.title,
            "event_date": sooner.event_date,
            "event_end_date": sooner.event_end_date,
            "event_type": sooner.event_type,
            "course": "Geral",
            "description": None,
            "location": sooner.location,
            "image_url": None,
            "link_url": None,
        },
        {
            "id": formerly_unpublished.id,
            "title": formerly_unpublished.title,
            "event_date": formerly_unpublished.event_date,
            "event_end_date": formerly_unpublished.event_end_date,
            "event_type": formerly_unpublished.event_type,
            "course": "Geral",
            "description": None,
            "location": formerly_unpublished.location,
            "image_url": None,
            "link_url": None,
        },
        {
            "id": later.id,
            "title": later.title,
            "event_date": later.event_date,
            "event_end_date": later.event_end_date,
            "event_type": later.event_type,
            "course": "Geral",
            "description": later.description,
            "location": later.location,
            "image_url": later.image_url,
            "link_url": later.link_url,
        },
    ]
    assert "tenant_id" not in response.text
    assert "created_at" not in response.text
    assert "published" not in response.text
    assert finished_title not in response.text
    assert other_tenant.title not in response.text


def test_public_multiday_event_is_visible_through_last_day_and_removed_next_day(
    db: Session,
) -> None:
    event = CompanyEvent(
        tenant_id="period-tenant",
        title="Semana de integração",
        event_date="2026-09-28",
        event_end_date="2026-09-30",
        event_type="evento_social",
        location="Campus",
    )
    future = CompanyEvent(
        tenant_id="period-tenant",
        title="Evento futuro",
        event_date="2026-10-05",
        event_end_date="2026-10-05",
        event_type="palestra",
        location="Auditório",
    )
    db.add_all([event, future])
    db.commit()

    on_last_day = crud.get_public_events(db, "period-tenant", today=date(2026, 9, 30))
    assert [item.title for item in on_last_day] == [event.title, future.title]

    next_day = crud.get_public_events(db, "period-tenant", today=date(2026, 10, 1))
    assert [item.title for item in next_day] == [future.title]


def test_purge_expired_events_only_deletes_target_tenant(db: Session) -> None:
    expired_a = CompanyEvent(
        tenant_id="purge-a", title="Expirado A", event_date="2026-09-01",
        event_end_date="2026-09-10", event_type="outro", location="A",
    )
    active_a = CompanyEvent(
        tenant_id="purge-a", title="Ativo A", event_date="2026-09-20",
        event_end_date="2026-09-30", event_type="outro", location="A",
    )
    expired_b = CompanyEvent(
        tenant_id="purge-b", title="Expirado B", event_date="2026-09-01",
        event_end_date="2026-09-10", event_type="outro", location="B",
    )
    db.add_all([expired_a, active_a, expired_b])
    db.commit()

    assert crud.purge_expired_events(db, "purge-a", today=date(2026, 9, 30)) == 1
    assert db.query(CompanyEvent).filter(CompanyEvent.id == active_a.id).one()
    assert db.query(CompanyEvent).filter(CompanyEvent.id == expired_b.id).one()


def test_public_chat_uses_slug_and_rejects_client_supplied_tenant(
    client: TestClient,
) -> None:
    public_slug = client.get("/config").json()["public_slug"]

    response = client.post(
        f"/public/{public_slug}/chat",
        json={"message": "Como faço minha matrícula?"},
    )
    tampered = client.post(
        f"/public/{public_slug}/chat",
        json={"message": "Teste", "tenant_id": "outro-tenant"},
    )

    assert response.status_code == 200
    assert "Resposta simulada" in response.text
    assert tampered.status_code == 422
