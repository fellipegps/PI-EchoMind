"""Guia visual, publicação, fotos e isolamento institucional."""

from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app import campus_map_repository as geo
from app.campus_map_schemas import CampusCreate, CampusResponse
from app.campus_photo import normalize_photo
from app.database import (
    Campus, CampusBuilding, CampusLandmark, CampusPathEdge, CampusPathNode,
    CampusPlacePhoto, CampusSpace, Config,
)


def _create_campus(db, name="Campus Central"):
    row = geo.create_campus(db, "test-admin", {
        "name": name, "center_lat": -16.328, "center_lng": -48.951, "zoom": 17,
    })
    return CampusResponse.model_validate(row).model_dump()


def _building(db, campus_id, name="Bloco A"):
    row = geo.create_building(db, "test-admin", campus_id, {
        "name": name, "entrance_lat": -16.329, "entrance_lng": -48.951,
        "description": "Entrada pela praça central.",
    })
    return geo.place_data(db, row, "building")


def _places(client, db):
    campus = _create_campus(db)
    building = _building(db, campus["id"])
    space = geo.create_space(db, "test-admin", campus["id"], {
        "building_id": building["id"], "name": "Auditório 101", "kind": "auditorio",
        "floor": "1", "description": "Entrada ao lado da biblioteca.",
    })
    landmark = client.post(f"/campuses/{campus['id']}/landmarks", json={
        "name": "Praça central", "lat": -16.328, "lng": -48.952,
        "description": "Jardim em frente ao bloco A.",
    })
    assert landmark.status_code == 201, landmark.text
    slug = db.query(Config).filter_by(tenant_id="test-admin").one().public_slug
    return campus, {"building": building, "space": geo.place_data(db, space, "space"), "landmark": landmark.json()}, slug


def _image(color="red"):
    output = BytesIO()
    Image.new("RGB", (30, 20), color).save(output, format="PNG")
    return output.getvalue()


def _upload(client, campus_id, place_type, place, content=None):
    return client.post(f"/campuses/{campus_id}/places/{place_type}/{place['id']}/photos",
                       files={"file": ("foto.png", content or _image(), "image/png")},
                       data={"caption": "Vista da entrada"})


def _team_upload(db, campus_id, kind, place, content=None):
    photo, row = geo.add_photo(
        db, "test-admin", campus_id, kind, place["id"], normalize_photo(content or _image()), "Vista da entrada",
    )
    return geo.photo_data(photo, row, kind)


def test_guide_publishes_multiple_photos_from_team_and_administrator(client, db):
    campus, places, slug = _places(client, db)
    for place_type, place in places.items():
        if place_type == "landmark":
            upload = _upload(client, campus["id"], place_type, place)
            assert upload.status_code == 201
            first = upload.json()
            second = _upload(client, campus["id"], place_type, place, _image("blue")).json()
        else:
            first = _team_upload(db, campus["id"], place_type, place)
            second = _team_upload(db, campus["id"], place_type, place, _image("blue"))
        assert first["id"] != second["id"]
        assert client.get(first["url"]).headers["content-type"] == "image/jpeg"
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
    assert len(response.json()["landmarks"][0]["photos"]) == 2
    assert "entrance_node_id" not in response.text


def test_public_codes_survive_edits_and_moving_spaces(client, db):
    campus, places, slug = _places(client, db)
    second = _building(db, campus["id"], "Bloco B")
    for kind, resource in (("building", "buildings"), ("space", "spaces"), ("landmark", "landmarks")):
        place = places[kind]
        changes = {"name": "Novo nome"}
        if kind == "space":
            changes["building_id"] = second["id"]
        if kind == "landmark":
            edited = client.put(f"/campuses/{campus['id']}/{resource}/{place['id']}", json=changes)
            assert edited.status_code == 200, edited.text
            assert edited.json()["public_code"] == place["public_code"]
        else:
            update = geo.update_building if kind == "building" else geo.update_space
            assert update(db, "test-admin", campus["id"], place["id"], changes).public_code == place["public_code"]
        fiche = client.get(f"/public/{slug}/places/{kind}/{place['public_code']}").json()
        assert fiche["place"]["name"] == "Novo nome"
        if kind == "space":
            assert fiche["building"]["id"] == second["id"]


@pytest.mark.parametrize("hidden", ["campus", "building", "space", "landmark"])
def test_unpublished_places_and_their_images_are_not_public(client, db, hidden):
    campus, places, slug = _places(client, db)
    place_type = "space" if hidden in {"campus", "building", "space"} else "landmark"
    place = places[place_type]
    _team_upload(db, campus["id"], place_type, place)
    url = f"/public/{slug}/places/{place_type}/{place['public_code']}"
    photo_url = client.get(url).json()["place"]["photos"][0]["url"]
    if hidden == "campus":
        geo.update_campus(db, "test-admin", campus["id"], {"active": False})
    else:
        update = {"building": geo.update_building, "space": geo.update_space, "landmark": geo.update_landmark}[hidden]
        update(db, "test-admin", campus["id"], places[hidden]["id"], {"active": False})
    assert client.get(url).status_code == 404
    assert client.get(photo_url).status_code == 404
    public = client.get(f"/public/{slug}/geo-campus").json()
    assert not any(p["id"] == place["id"] for p in public[{"space": "spaces", "landmark": "landmarks"}[place_type]])


def test_cross_tenant_campus_and_photo_references_are_rejected(client, db):
    campus, places, slug = _places(client, db)
    second = _create_campus(db, "Campus Dois")
    place = places["building"]
    photo = _team_upload(db, campus["id"], "building", place)
    with pytest.raises(geo.GeoNotFoundError):
        geo.create_space(db, "test-admin", second["id"], {
            "building_id": place["id"], "name": "Lab", "kind": "laboratorio",
        })
    assert client.get(f"/campuses/{second['id']}/buildings/{place['id']}").status_code == 404
    landmark = places["landmark"]
    assert _upload(client, second["id"], "landmark", landmark).status_code == 404
    assert client.delete(f"/campuses/{second['id']}/places/landmark/{landmark['id']}/photos/{photo['id']}").status_code == 404
    foreign_campus = Campus(id="foreign", tenant_id="foreign", name="Externo", center_lat=0, center_lng=0)
    db.add(foreign_campus)
    db.flush()
    foreign = CampusBuilding(tenant_id="foreign", campus_id="foreign", name="Bloco externo",
                             entrance_lat=0, entrance_lng=0)
    db.add(foreign)
    db.commit()
    assert client.get(f"/public/{slug}/places/building/{foreign.public_code}").status_code == 404
    assert _upload(client, foreign_campus.id, "landmark", landmark).status_code == 404
    wrong_place = f"/public/{slug}/places/landmark/{places['landmark']['public_code']}/photos/{photo['id']}"
    assert client.get(wrong_place).status_code == 404
    assert db.query(CampusPlacePhoto).count() == 1


def test_photos_validate_content_size_and_strip_trailing_payload(client, db):
    campus, places, _slug = _places(client, db)
    url = f"/campuses/{campus['id']}/places/landmark/{places['landmark']['id']}/photos"
    assert client.post(url, files={"file": ("bad.png", b"<svg/>", "image/png")}).status_code == 422
    assert client.post(url, files={"file": ("big.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")}).status_code == 413
    response = _upload(client, campus["id"], "landmark", places["landmark"], _image() + b"<script>alert(1)</script>")
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
    first = _upload(client, campus["id"], "landmark", places["landmark"]).json()
    second = _upload(client, campus["id"], "landmark", places["landmark"]).json()
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
        _team_upload(db, campus["id"], kind, place)
    assert db.query(CampusPlacePhoto).count() == 3
    geo.delete_building(db, "test-admin", campus["id"], places["building"]["id"])
    assert db.query(CampusPlacePhoto).count() == 1
    assert db.query(CampusSpace).count() == 0
    geo.delete_campus(db, "test-admin", campus["id"])
    for model in (Campus, CampusBuilding, CampusSpace, CampusLandmark, CampusPlacePhoto):
        assert db.query(model).filter_by(tenant_id="test-admin").count() == 0


def test_validation_and_retired_routing_endpoints(client, db):
    campus = _create_campus(db)
    with pytest.raises(ValidationError):
        CampusCreate(name="Xx", center_lat=91, center_lng=0)
    with pytest.raises(ValidationError):
        CampusCreate(name="Xx", center_lat=0, center_lng=0, tenant_id="forged")
    with pytest.raises(geo.GeoConflictError):
        _create_campus(db, "campus central")
    paths = client.get("/openapi.json").json()["paths"]
    assert all("path-nodes" not in p and "path-edges" not in p for p in paths)
    assert client.post(f"/campuses/{campus['id']}/path-nodes", json={"lat": 0, "lng": 0}).status_code == 404
    assert client.get(f"/campuses/{campus['id']}/path-edges").status_code == 404


def test_legacy_paths_and_registered_places_remain_in_database(client, db):
    campus = _create_campus(db)
    first = CampusPathNode(id="a", tenant_id="test-admin", campus_id=campus["id"], lat=0, lng=0)
    second = CampusPathNode(id="b", tenant_id="test-admin", campus_id=campus["id"], lat=0, lng=1)
    db.add_all([first, second])
    db.flush()
    edge = CampusPathEdge(tenant_id="test-admin", campus_id=campus["id"], from_node_id="a", to_node_id="b")
    db.add(edge)
    db.commit()
    building = _building(db, campus["id"])
    geo.update_building(db, "test-admin", campus["id"], building["id"], {"name": "Bloco atualizado"})
    assert db.query(CampusPathNode).count() == 2
    assert db.query(CampusPathEdge).count() == 1
    geo.delete_campus(db, "test-admin", campus["id"])


def test_admin_edits_content_without_modifying_campus_or_geometry(client, db):
    campus, places, slug = _places(client, db)
    campus_path = f"/campuses/{campus['id']}"
    block_path = campus_path + f"/buildings/{places['building']['id']}"
    space_path = campus_path + f"/spaces/{places['space']['id']}"
    assert client.post("/campuses", json={}).status_code == 405
    assert client.put(campus_path, json={}).status_code == 405
    for path in (campus_path, block_path, space_path):
        assert client.delete(path).status_code == 405
    assert client.post(f"{campus_path}/buildings", json={}).status_code == 405
    assert client.put(block_path, json={"name": "Novo nome", "entrance_lat": 0}).status_code == 422
    assert client.put(space_path, json={"building_id": "outro"}).status_code == 422
    assert client.put(block_path, json={"name": "Novo nome"}).status_code == 200
    assert client.put(space_path, json={"description": "Descrição atualizada"}).status_code == 200
    assert client.post(f"{campus_path}/spaces", json={"building_id": "outro", "name": "Sala"}).status_code == 404
    for kind in ("building", "space"):
        result = _upload(client, campus["id"], kind, places[kind])
        assert result.status_code == 201
        photo = result.json()
        assert client.get(photo["url"]).status_code == 200
        assert client.delete(photo["url"]).status_code == 204
    public = client.get(f"/public/{slug}/places/building/{places['building']['public_code']}").json()
    assert public["place"]["name"] == "Novo nome"
    assert public["spaces"][0]["description"] == "Descrição atualizada"
    landmark = places["landmark"]
    assert client.delete(f"{campus_path}/landmarks/{landmark['id']}").status_code == 204


def test_anapolis_catalog_prepares_existing_blocks_and_preserves_later_edits(client, db):
    campus, places, slug = _places(client, db)
    campus_id = campus["id"]
    bootstrap = f"/campuses/{campus_id}/model-defaults"
    assert client.post(bootstrap).status_code == 204
    assert len(client.get(f"/campuses/{campus_id}/buildings").json()) == 1
    geo.update_campus(db, "test-admin", campus_id, {"model_key": "anapolis"})
    assert client.post(bootstrap).status_code == 204
    buildings = {row["model_destination_id"]: row for row in client.get(f"/campuses/{campus_id}/buildings").json()}
    assert len(buildings) == 12
    assert buildings["bloco-a"]["id"] == places["building"]["id"]
    labs = client.get(f"/campuses/{campus_id}/spaces").json()
    lab = next(row for row in labs if row["building_id"] == buildings["biblioteca"]["id"])
    assert client.put(f"/campuses/{campus_id}/spaces/{lab['id']}", json={"name": "Novo laboratório", "description": "Acesso restrito"}).status_code == 200
    assert client.put(f"/campuses/{campus_id}/buildings/{places['building']['id']}", json={"name": "Bloco de Saúde"}).status_code == 200
    assert client.post(bootstrap).status_code == 204
    after = client.get(f"/public/{slug}/geo-campus").json()
    assert len(after["buildings"]) == 12 and len(after["spaces"]) == len(labs)
    assert next(block for block in after["buildings"] if block["model_destination_id"] == "bloco-a")["name"] == "Bloco de Saúde"
    assert next(space for space in after["spaces"] if space["id"] == lab["id"])["description"] == "Acesso restrito"


def test_team_manifest_reuses_existing_campus_block_and_photo(client, db, tmp_path):
    from scripts.configure_campus import CampusManifest, publish_campus

    campus, places, slug = _places(client, db)
    (tmp_path / "foto.png").write_bytes(_image())
    manifest = CampusManifest.model_validate({
        "name": campus["name"], "center_lat": campus["center_lat"], "center_lng": campus["center_lng"],
        "model_key": "anapolis",
        "buildings": [{
            "id": places["building"]["id"], "name": "Novo nome do bloco", "model_destination_id": "bloco-a",
            "entrance_lat": -16.329, "entrance_lng": -48.951, "photos": [{"file": "foto.png", "caption": "Fachada"}],
        }],
    })

    assert publish_campus(db, slug, manifest, tmp_path, None) == campus["id"]
    assert publish_campus(db, slug, manifest, tmp_path, campus["id"]) == campus["id"]
    data = client.get(f"/public/{slug}/geo-campus").json()
    assert data["campuses"][0]["model_key"] == "anapolis"
    assert len(data["buildings"]) == 1
    assert data["buildings"][0]["model_destination_id"] == "bloco-a"
    assert data["buildings"][0]["public_code"] == places["building"]["public_code"]
    assert len(data["buildings"][0]["photos"]) == 1
    assert client.get(data["buildings"][0]["photos"][0]["url"]).status_code == 200
