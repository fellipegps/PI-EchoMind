"""Fluxo administrativo, publicação e isolamento do mapa geográfico."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import Campus, CampusBuilding, CampusPathEdge, CampusPathNode, CampusSpace, Config


def _create_campus(client: TestClient, name: str = "Campus Central") -> dict:
    response = client.post("/campuses", json={
        "name": name,
        "center_lat": -16.328,
        "center_lng": -48.951,
        "zoom": 17,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _create_node(client: TestClient, campus_id: str, lat: float, lng: float) -> dict:
    response = client.post(f"/campuses/{campus_id}/path-nodes", json={"lat": lat, "lng": lng})
    assert response.status_code == 201, response.text
    return response.json()


def test_administrator_can_publish_building_spaces_and_walkable_path(
    client: TestClient, db: Session,
) -> None:
    campus = _create_campus(client)
    campus_id = campus["id"]
    start = _create_node(client, campus_id, -16.328, -48.951)
    entrance = _create_node(client, campus_id, -16.329, -48.951)
    edge = client.post(f"/campuses/{campus_id}/path-edges", json={
        "from_node_id": entrance["id"], "to_node_id": start["id"], "accessible": True,
    })
    assert edge.status_code == 201, edge.text
    assert edge.json()["distance_m"] > 100

    building = client.post(f"/campuses/{campus_id}/buildings", json={
        "name": "Bloco A", "category": "bloco", "entrance_lat": -16.329,
        "entrance_lng": -48.951, "entrance_node_id": entrance["id"],
        "description": "Entrada pela praça central.",
    })
    assert building.status_code == 201, building.text
    building_id = building.json()["id"]
    space = client.post(f"/campuses/{campus_id}/spaces", json={
        "building_id": building_id, "name": "Auditório 101", "kind": "auditorio",
        "floor": "1", "description": "Capacidade para 150 pessoas.",
    })
    assert space.status_code == 201, space.text

    slug = db.query(Config).filter(Config.tenant_id == "test-admin").one().public_slug
    public = client.get(f"/public/{slug}/geo-campus")
    assert public.status_code == 200, public.text
    data = public.json()
    assert [item["id"] for item in data["campuses"]] == [campus_id]
    assert [item["id"] for item in data["buildings"]] == [building_id]
    assert [item["id"] for item in data["spaces"]] == [space.json()["id"]]
    assert {item["id"] for item in data["nodes"]} == {start["id"], entrance["id"]}
    assert [item["id"] for item in data["edges"]] == [edge.json()["id"]]
    assert "tenant_id" not in public.text

    moved = client.put(f"/campuses/{campus_id}/path-nodes/{entrance['id']}", json={
        "lat": -16.330,
    })
    assert moved.status_code == 200
    updated_edge = client.get(f"/campuses/{campus_id}/path-edges/{edge.json()['id']}")
    assert updated_edge.json()["distance_m"] > edge.json()["distance_m"]
    reverse_duplicate = client.post(f"/campuses/{campus_id}/path-edges", json={
        "from_node_id": start["id"], "to_node_id": entrance["id"],
    })
    assert reverse_duplicate.status_code == 409


def test_cross_campus_and_cross_tenant_references_are_rejected(
    client: TestClient, db: Session,
) -> None:
    first = _create_campus(client, "Campus Um")
    second = _create_campus(client, "Campus Dois")
    first_node = _create_node(client, first["id"], -16.328, -48.951)
    second_node = _create_node(client, second["id"], -16.328, -48.952)
    other_tenant_node = CampusPathNode(
        tenant_id="other-tenant", campus_id="other-campus", lat=-16.3, lng=-48.9,
    )
    other_tenant_campus = Campus(
        id="other-campus", tenant_id="other-tenant", name="Campus Externo",
        center_lat=-16.3, center_lng=-48.9,
    )
    db.add_all([other_tenant_campus, other_tenant_node])
    db.commit()

    for foreign_node_id in (second_node["id"], other_tenant_node.id):
        bad_edge = client.post(f"/campuses/{first['id']}/path-edges", json={
            "from_node_id": first_node["id"], "to_node_id": foreign_node_id,
        })
        assert bad_edge.status_code == 404
        bad_building = client.post(f"/campuses/{first['id']}/buildings", json={
            "name": "Prédio inválido", "entrance_lat": -16.328,
            "entrance_lng": -48.951, "entrance_node_id": foreign_node_id,
        })
        assert bad_building.status_code == 404

    first_building = client.post(f"/campuses/{first['id']}/buildings", json={
        "name": "Bloco A", "entrance_lat": -16.328, "entrance_lng": -48.951,
    }).json()
    assert client.post(f"/campuses/{second['id']}/spaces", json={
        "building_id": first_building["id"], "name": "Laboratório", "kind": "laboratorio",
    }).status_code == 404
    assert client.get(f"/campuses/{second['id']}/buildings/{first_building['id']}").status_code == 404
    assert client.put(f"/campuses/{second['id']}/buildings/{first_building['id']}", json={
        "name": "Hack",
    }).status_code == 404
    assert client.delete(f"/campuses/{second['id']}/buildings/{first_building['id']}").status_code == 404


def test_visibility_validation_and_scoped_cascade(client: TestClient, db: Session) -> None:
    assert client.post("/campuses", json={
        "name": "Campus", "center_lat": 91, "center_lng": 0,
    }).status_code == 422
    assert client.post("/campuses", json={
        "name": "Campus", "center_lat": 0, "center_lng": 0,
        "tenant_id": "forged",
    }).status_code == 422

    campus = _create_campus(client)
    campus_id = campus["id"]
    duplicate = client.post("/campuses", json={
        "name": "campus central", "center_lat": -16.328, "center_lng": -48.951,
    })
    assert duplicate.status_code == 409

    first_node = _create_node(client, campus_id, -16.328, -48.951)
    second_node = _create_node(client, campus_id, -16.329, -48.951)
    edge = client.post(f"/campuses/{campus_id}/path-edges", json={
        "from_node_id": first_node["id"], "to_node_id": second_node["id"],
    }).json()
    building = client.post(f"/campuses/{campus_id}/buildings", json={
        "name": "Bloco A", "entrance_lat": -16.328, "entrance_lng": -48.951,
        "entrance_node_id": first_node["id"],
    }).json()
    space = client.post(f"/campuses/{campus_id}/spaces", json={
        "building_id": building["id"], "name": "Lab 1", "kind": "laboratorio",
    }).json()

    slug = db.query(Config).filter(Config.tenant_id == "test-admin").one().public_slug
    assert client.put(f"/campuses/{campus_id}/path-edges/{edge['id']}", json={
        "active": False,
    }).status_code == 200
    assert client.put(f"/campuses/{campus_id}/spaces/{space['id']}", json={
        "active": False,
    }).status_code == 200
    public = client.get(f"/public/{slug}/geo-campus").json()
    assert public["edges"] == []
    assert public["spaces"] == []
    assert {node["id"] for node in public["nodes"]} == {first_node["id"]}

    assert client.put(f"/campuses/{campus_id}/buildings/{building['id']}", json={
        "active": False,
    }).status_code == 200
    hidden_building = client.get(f"/public/{slug}/geo-campus").json()
    assert hidden_building["buildings"] == []
    assert hidden_building["nodes"] == []
    assert client.put(f"/campuses/{campus_id}/buildings/{building['id']}", json={
        "active": True,
    }).status_code == 200
    assert client.put(f"/campuses/{campus_id}", json={"active": False}).status_code == 200
    hidden_campus = client.get(f"/public/{slug}/geo-campus").json()
    assert hidden_campus == {"campuses": [], "buildings": [], "spaces": [], "nodes": [], "edges": []}
    assert client.put(f"/campuses/{campus_id}", json={"active": True}).status_code == 200

    assert client.delete(f"/campuses/{campus_id}/path-nodes/{first_node['id']}").status_code == 204
    updated_building = client.get(f"/campuses/{campus_id}/buildings/{building['id']}").json()
    assert updated_building["entrance_node_id"] is None
    assert client.get(f"/campuses/{campus_id}/path-edges").json() == []
    assert client.delete(f"/campuses/{campus_id}").status_code == 204
    assert client.get(f"/campuses/{campus_id}").status_code == 404
    assert db.query(CampusBuilding).filter_by(tenant_id="test-admin", campus_id=campus_id).count() == 0
    assert db.query(CampusSpace).filter_by(tenant_id="test-admin", campus_id=campus_id).count() == 0
    assert db.query(CampusPathNode).filter_by(tenant_id="test-admin", campus_id=campus_id).count() == 0
    assert db.query(CampusPathEdge).filter_by(tenant_id="test-admin", campus_id=campus_id).count() == 0
