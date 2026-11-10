"""Guia visual, publicação, fotos e isolamento institucional."""

from io import BytesIO

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.database import (
    Campus, CampusBuilding, CampusLandmark, CampusPathEdge, CampusPathNode,
    CampusPlacePhoto, CampusSpace, Config,
)


def _create_campus(client: TestClient, name: str = "Campus Central") -> dict:
    response = client.post("/campuses", json={
        "name": name, "center_lat": -16.328, "center_lng": -48.951, "zoom": 17,
    })
    assert response.status_code == 201, response.text
    return response.json()


def _building(client, campus_id, name="Bloco A"):
    response = client.post(f"/campuses/{campus_id}/buildings", json={
        "name": name, "entrance_lat": -16.329, "entrance_lng": -48.951,
        "description": "Entrada pela praça central.",
    })
    assert response.status_code == 201, response.text
    return response.json()


def _places(client, db):
    campus = _create_campus(client)
    building = _building(client, campus["id"])
    space = client.post(f"/campuses/{campus['id']}/spaces", json={
        "building_id": building["id"], "name": "Auditório 101", "kind": "auditorio",
        "floor": "1", "description": "Entrada ao lado da biblioteca.",
    })
    landmark = client.post(f"/campuses/{campus['id']}/landmarks", json={
        "name": "Praça central", "lat": -16.328, "lng": -48.952,
        "description": "Jardim em frente ao bloco A.",
    })
    assert space.status_code == landmark.status_code == 201
    slug = db.query(Config).filter_by(tenant_id="test-admin").one().public_slug
    return campus, {"building": building, "space": space.json(), "landmark": landmark.json()}, slug


def _image(color="red"):
    output = BytesIO()
    Image.new("RGB", (30, 20), color).save(output, format="PNG")
    return output.getvalue()


def _upload(client, campus_id, place_type, place, content=None):
    return client.post(f"/campuses/{campus_id}/places/{place_type}/{place['id']}/photos",
                       files={"file": ("foto.png", content or _image(), "image/png")},
                       data={"caption": "Vista da entrada"})


def test_administrator_can_publish_visual_places_and_multiple_photos(client, db):
    campus, places, slug = _places(client, db)
    for place_type, place in places.items():
        first = _upload(client, campus["id"], place_type, place)
        second = _upload(client, campus["id"], place_type, place, _image("blue"))
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] != second.json()["id"]
        assert client.get(first.json()["url"]).headers["content-type"] == "image/jpeg"
        fiche = client.get(f"/public/{slug}/places/{place_type}/{place['public_code']}")
        assert fiche.status_code == 200, fiche.text
        data = fiche.json()
        assert data["place"]["public_code"] == place["public_code"]
        assert data["type"] == place_type
        assert [p["sort_order"] for p in data["place"]["photos"]] == [0, 1]
        assert "tenant_id" not in fiche.text
        assert "content" not in data["place"]["photos"][0]
        if place_type == "space":
            assert data["building"]["id"] == places["building"]["id"]
        else:
            assert data["building"] is None
        photo = client.get(data["place"]["photos"][0]["url"])
        assert photo.status_code == 200
        assert photo.headers["cache-control"] == "no-store"
        assert photo.headers["x-content-type-options"] == "nosniff"
    response = client.get(f"/public/{slug}/geo-campus")
    assert response.status_code == 200
    assert set(response.json()) == {"campuses", "buildings", "spaces", "landmarks"}
    assert len(response.json()["buildings"][0]["photos"]) == 2
    assert "entrance_node_id" not in response.text


def test_public_codes_survive_edits_and_moving_spaces(client, db):
    campus, places, slug = _places(client, db)
    second = _building(client, campus["id"], "Bloco B")
    for kind, resource in (("building", "buildings"), ("space", "spaces"), ("landmark", "landmarks")):
        place = places[kind]
        changes = {"name": "Novo nome"}
        if kind == "space":
            changes["building_id"] = second["id"]
        edited = client.put(f"/campuses/{campus['id']}/{resource}/{place['id']}", json=changes)
        assert edited.status_code == 200, edited.text
        assert edited.json()["public_code"] == place["public_code"]
        fiche = client.get(f"/public/{slug}/places/{kind}/{place['public_code']}").json()
        assert fiche["place"]["name"] == "Novo nome"
        if kind == "space":
            assert fiche["building"]["id"] == second["id"]


@pytest.mark.parametrize("hidden", ["campus", "building", "space", "landmark"])
def test_unpublished_places_and_their_images_are_not_public(client, db, hidden):
    campus, places, slug = _places(client, db)
    place_type = "space" if hidden in {"campus", "building", "space"} else "landmark"
    place = places[place_type]
    assert _upload(client, campus["id"], place_type, place).status_code == 201
    url = f"/public/{slug}/places/{place_type}/{place['public_code']}"
    photo_url = client.get(url).json()["place"]["photos"][0]["url"]
    path = f"/campuses/{campus['id']}"
    if hidden != "campus":
        resources = {"building": "buildings", "space": "spaces", "landmark": "landmarks"}
        path += f"/{resources[hidden]}/{places[hidden]['id']}"
    assert client.put(path, json={"active": False}).status_code == 200
    assert client.get(url).status_code == 404
    assert client.get(photo_url).status_code == 404
    public = client.get(f"/public/{slug}/geo-campus").json()
    assert not any(p["id"] == place["id"] for p in public[{"space": "spaces", "landmark": "landmarks"}[place_type]])


def test_cross_tenant_campus_and_photo_references_are_rejected(client, db):
    campus, places, slug = _places(client, db)
    second = _create_campus(client, "Campus Dois")
    place = places["building"]
    photo = _upload(client, campus["id"], "building", place).json()
    assert client.post(f"/campuses/{second['id']}/spaces", json={
        "building_id": place["id"], "name": "Lab", "kind": "laboratorio",
    }).status_code == 404
    assert client.get(f"/campuses/{second['id']}/buildings/{place['id']}").status_code == 404
    assert _upload(client, second["id"], "building", place).status_code == 404
    assert client.delete(f"/campuses/{second['id']}/places/building/{place['id']}/photos/{photo['id']}").status_code == 404
    foreign_campus = Campus(id="foreign", tenant_id="foreign", name="Externo", center_lat=0, center_lng=0)
    db.add(foreign_campus)
    db.flush()
    foreign = CampusBuilding(tenant_id="foreign", campus_id="foreign", name="Bloco externo",
                             entrance_lat=0, entrance_lng=0)
    db.add(foreign)
    db.commit()
    assert client.get(f"/public/{slug}/places/building/{foreign.public_code}").status_code == 404
    assert _upload(client, foreign_campus.id, "building", {"id": foreign.id}).status_code == 404
    wrong_place = f"/public/{slug}/places/landmark/{places['landmark']['public_code']}/photos/{photo['id']}"
    assert client.get(wrong_place).status_code == 404
    assert db.query(CampusPlacePhoto).count() == 1


def test_photos_validate_content_size_and_strip_trailing_payload(client, db):
    campus, places, _slug = _places(client, db)
    url = f"/campuses/{campus['id']}/places/building/{places['building']['id']}/photos"
    assert client.post(url, files={"file": ("bad.png", b"<svg/>", "image/png")}).status_code == 422
    assert client.post(url, files={"file": ("big.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")}).status_code == 413
    response = _upload(client, campus["id"], "building", places["building"], _image() + b"<script>alert(1)</script>")
    assert response.status_code == 201
    data = client.get(response.json()["url"]).content
    assert b"<script>" not in data
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert not image.getexif()
    assert db.query(CampusPlacePhoto).count() == 1


@pytest.mark.parametrize("format_name", ["JPEG", "PNG", "WEBP"])
def test_normalized_photo_formats_and_phone_resolution(format_name):
    from app.campus_photo import normalize_photo

    output = BytesIO()
    Image.new("RGB", (4032, 3024), "white").save(output, format=format_name)
    data = normalize_photo(output.getvalue())
    with Image.open(BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 3200


def test_photo_pixel_bound_is_checked_before_decoding_full_image():
    from app.campus_photo import InvalidPhoto, normalize_photo

    output = BytesIO()
    Image.new("RGB", (5000, 3300), "white").save(output, format="PNG")
    with pytest.raises(InvalidPhoto, match="16 megapixels"):
        normalize_photo(output.getvalue())


def test_upload_retry_is_idempotent_and_photo_bytes_are_deferred(client, db):
    campus, places, _slug = _places(client, db)
    first = _upload(client, campus["id"], "building", places["building"]).json()
    second = _upload(client, campus["id"], "building", places["building"]).json()
    assert first["id"] == second["id"]
    db.expunge_all()
    row = db.query(CampusPlacePhoto).one()
    assert "content" in inspect(row).unloaded
    assert client.get(first["url"]).status_code == 200
    assert client.delete(first["url"]).status_code == 204
    assert client.get(first["url"]).status_code == 404


def test_deleting_a_block_or_campus_cascades_photos_in_the_same_transaction(client, db):
    campus, places, _slug = _places(client, db)
    for kind, place in places.items():
        assert _upload(client, campus["id"], kind, place).status_code == 201
    assert db.query(CampusPlacePhoto).count() == 3
    assert client.delete(f"/campuses/{campus['id']}/buildings/{places['building']['id']}").status_code == 204
    assert db.query(CampusPlacePhoto).count() == 1
    assert db.query(CampusSpace).count() == 0
    assert client.delete(f"/campuses/{campus['id']}").status_code == 204
    for model in (Campus, CampusBuilding, CampusSpace, CampusLandmark, CampusPlacePhoto):
        assert db.query(model).filter_by(tenant_id="test-admin").count() == 0


def test_validation_and_retired_routing_endpoints(client, db):
    campus = _create_campus(client)
    assert client.post("/campuses", json={"name": "Xx", "center_lat": 91, "center_lng": 0}).status_code == 422
    assert client.post("/campuses", json={"name": "Xx", "center_lat": 0, "center_lng": 0, "tenant_id": "forged"}).status_code == 422
    assert client.post("/campuses", json={"name": "campus central", "center_lat": 0, "center_lng": 0}).status_code == 409
    paths = client.get("/openapi.json").json()["paths"]
    assert all("path-nodes" not in p and "path-edges" not in p for p in paths)
    assert client.post(f"/campuses/{campus['id']}/path-nodes", json={"lat": 0, "lng": 0}).status_code == 404
    assert client.get(f"/campuses/{campus['id']}/path-edges").status_code == 404


def test_legacy_paths_and_registered_places_remain_in_database(client, db):
    campus = _create_campus(client)
    first = CampusPathNode(id="a", tenant_id="test-admin", campus_id=campus["id"], lat=0, lng=0)
    second = CampusPathNode(id="b", tenant_id="test-admin", campus_id=campus["id"], lat=0, lng=1)
    db.add_all([first, second])
    db.flush()
    edge = CampusPathEdge(tenant_id="test-admin", campus_id=campus["id"], from_node_id="a", to_node_id="b")
    db.add(edge)
    db.commit()
    building = _building(client, campus["id"])
    assert client.put(f"/campuses/{campus['id']}/buildings/{building['id']}", json={"name": "Bloco atualizado"}).status_code == 200
    assert db.query(CampusPathNode).count() == 2
    assert db.query(CampusPathEdge).count() == 1
    assert client.delete(f"/campuses/{campus['id']}").status_code == 204
