"""Contrato público por slug, sem exposição ou confiança no tenant interno."""

from __future__ import annotations

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
        show_on_totem=True,
        total_consults=42,
    )
    faq_b = Faq(
        tenant_id="tenant-b",
        question="Pergunta exclusiva do tenant B?",
        answer="Resposta exclusiva do tenant B.",
        show_on_totem=True,
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


def test_public_events_are_published_current_ordered_and_tenant_scoped(
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
        event_type="palestra",
        description="Segundo na ordenação.",
        location="Auditório B",
        published=True,
    )
    sooner = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento mais próximo",
        event_date="2099-01-10",
        event_type="workshop",
        description=None,
        location="Laboratório 1",
        published=True,
    )
    unpublished = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Rascunho interno",
        event_date="2099-01-01",
        event_type="reuniao",
        location="Sala interna",
        published=False,
    )
    finished = CompanyEvent(
        tenant_id=config_a.tenant_id,
        title="Evento encerrado",
        event_date="2000-01-01",
        event_type="outro",
        location="Arquivo",
        published=True,
    )
    other_tenant = CompanyEvent(
        tenant_id=config_b.tenant_id,
        title="Evento do tenant B",
        event_date="2099-01-02",
        event_type="outro",
        location="Outro campus",
        published=True,
    )
    db.add_all(
        [
            config_a,
            config_b,
            later,
            sooner,
            unpublished,
            finished,
            other_tenant,
        ]
    )
    db.commit()

    response = client.get(f"/public/{config_a.public_slug}/events")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": sooner.id,
            "title": sooner.title,
            "event_date": sooner.event_date,
            "event_type": sooner.event_type,
            "description": None,
            "location": sooner.location,
        },
        {
            "id": later.id,
            "title": later.title,
            "event_date": later.event_date,
            "event_type": later.event_type,
            "description": later.description,
            "location": later.location,
        },
    ]
    assert "tenant_id" not in response.text
    assert unpublished.title not in response.text
    assert finished.title not in response.text
    assert other_tenant.title not in response.text


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
