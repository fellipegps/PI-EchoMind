"""CRUD e contrato público dos locais do campus por tenant."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import CampusLocation, Config


LOCATION_PAYLOAD = {
    "name": "Biblioteca Central",
    "description": "Acervo e salas de estudo.",
    "category": "estudo",
    "floor": "Térreo",
    "building": "Bloco B",
    "x": 35.5,
    "y": 42.0,
    "active": True,
}


def test_admin_location_crud_is_tenant_scoped_and_hides_tenant(
    client: TestClient,
    db: Session,
) -> None:
    created = client.post("/locations", json=LOCATION_PAYLOAD)

    assert created.status_code == 201
    assert created.json()["name"] == LOCATION_PAYLOAD["name"]
    assert "tenant_id" not in created.json()
    location_id = created.json()["id"]

    listed = client.get("/locations")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [location_id]

    updated = client.put(
        f"/locations/{location_id}",
        json={"floor": "1º andar", "active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["floor"] == "1º andar"
    assert updated.json()["active"] is False

    other = CampusLocation(
        tenant_id="other-tenant",
        name="Local privado",
        category="administrativo",
        x=10,
        y=10,
    )
    db.add(other)
    db.commit()

    assert client.put(
        f"/locations/{other.id}",
        json={"name": "Tentativa indevida"},
    ).status_code == 404
    assert client.delete(f"/locations/{other.id}").status_code == 404

    deleted = client.delete(f"/locations/{location_id}")
    assert deleted.status_code == 204
    assert client.get("/locations").json() == []


def test_location_validates_coordinates_duplicates_and_rejects_client_tenant(
    client: TestClient,
) -> None:
    assert client.post(
        "/locations",
        json={**LOCATION_PAYLOAD, "tenant_id": "forged-tenant"},
    ).status_code == 422
    assert client.post(
        "/locations",
        json={**LOCATION_PAYLOAD, "x": 101},
    ).status_code == 422

    assert client.post("/locations", json=LOCATION_PAYLOAD).status_code == 201
    duplicate = client.post(
        "/locations",
        json={**LOCATION_PAYLOAD, "name": "biblioteca central"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Já existe um local com esse nome."}


def test_location_normalizes_text_and_rejects_blank_required_fields(
    client: TestClient,
) -> None:
    created = client.post(
        "/locations",
        json={
            **LOCATION_PAYLOAD,
            "name": "  Biblioteca Setorial  ",
            "description": "   ",
            "category": "  estudo  ",
            "floor": "  1º andar  ",
            "building": "  Bloco C  ",
        },
    )

    assert created.status_code == 201
    assert created.json()["name"] == "Biblioteca Setorial"
    assert created.json()["description"] is None
    assert created.json()["category"] == "estudo"
    assert created.json()["floor"] == "1º andar"
    assert created.json()["building"] == "Bloco C"
    assert client.post(
        "/locations",
        json={**LOCATION_PAYLOAD, "name": "   "},
    ).status_code == 422


def test_public_locations_return_only_active_rows_from_resolved_tenant(
    client: TestClient,
    db: Session,
) -> None:
    config_a = Config(
        tenant_id="locations-tenant-a",
        public_slug="campus-a-1234567890abcdef",
        company_name="Campus A",
    )
    config_b = Config(
        tenant_id="locations-tenant-b",
        public_slug="campus-b-1234567890abcdef",
        company_name="Campus B",
    )
    active_a = CampusLocation(
        tenant_id=config_a.tenant_id,
        name="Auditório Central",
        description="Eventos institucionais.",
        category="auditorio",
        floor="Térreo",
        building="Bloco A",
        x=20,
        y=30,
        active=True,
    )
    inactive_a = CampusLocation(
        tenant_id=config_a.tenant_id,
        name="Sala desativada",
        category="sala",
        x=40,
        y=50,
        active=False,
    )
    active_b = CampusLocation(
        tenant_id=config_b.tenant_id,
        name="Local do tenant B",
        category="outro",
        x=60,
        y=70,
        active=True,
    )
    db.add_all([config_a, config_b, active_a, inactive_a, active_b])
    db.commit()

    response = client.get(f"/public/{config_a.public_slug}/locations")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": active_a.id,
            "name": active_a.name,
            "description": active_a.description,
            "category": active_a.category,
            "floor": active_a.floor,
            "building": active_a.building,
            "x": active_a.x,
            "y": active_a.y,
        }
    ]
    assert "tenant_id" not in response.text
    assert inactive_a.name not in response.text
    assert active_b.name not in response.text
