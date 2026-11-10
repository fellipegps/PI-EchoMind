"""Verifica integridade e RLS do mapa geográfico no PostgreSQL descartável."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


pytestmark = pytest.mark.integration

GEO_TABLES = (
    "campuses", "campus_buildings", "campus_spaces",
    "campus_path_nodes", "campus_path_edges", "campus_landmarks", "campus_place_photos",
)


def test_geographic_tables_have_rls_and_tenant_scoped_foreign_keys(
    postgres_engine: Engine,
) -> None:
    inspector = inspect(postgres_engine)
    assert set(GEO_TABLES) <= set(inspector.get_table_names(schema="public"))

    with postgres_engine.connect() as connection:
        enabled = dict(connection.execute(text(
            "SELECT c.relname, c.relrowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname IN "
            "('campuses', 'campus_buildings', 'campus_spaces', "
            "'campus_path_nodes', 'campus_path_edges', 'campus_landmarks', 'campus_place_photos')"
        )).all())
    assert enabled == {table: True for table in GEO_TABLES}

    for table in ("campus_buildings", "campus_spaces", "campus_path_nodes", "campus_path_edges", "campus_landmarks"):
        foreign_keys = inspector.get_foreign_keys(table)
        assert any(
            set(fk["constrained_columns"]) == {"campus_id", "tenant_id"}
            and fk["referred_table"] == "campuses"
            for fk in foreign_keys
        )

    building_fks = inspector.get_foreign_keys("campus_buildings")
    assert any(
        set(fk["constrained_columns"]) == {"entrance_node_id", "tenant_id", "campus_id"}
        and fk["referred_table"] == "campus_path_nodes"
        for fk in building_fks
    )
    space_fks = inspector.get_foreign_keys("campus_spaces")
    assert any(
        set(fk["constrained_columns"]) == {"building_id", "tenant_id", "campus_id"}
        and fk["referred_table"] == "campus_buildings"
        for fk in space_fks
    )
    edge_fks = inspector.get_foreign_keys("campus_path_edges")
    assert {
        frozenset(fk["constrained_columns"])
        for fk in edge_fks if fk["referred_table"] == "campus_path_nodes"
    } == {
        frozenset({"from_node_id", "tenant_id", "campus_id"}),
        frozenset({"to_node_id", "tenant_id", "campus_id"}),
    }


def test_visual_guide_migration_preserves_registered_places_and_legacy_paths(postgres_engine: Engine) -> None:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    key = str(uuid4())
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config.attributes["connection"] = connection
            command.downgrade(config, "0027")
            connection.execute(text(
                "INSERT INTO campuses (id, tenant_id, name, center_lat, center_lng, created_at, updated_at) "
                "VALUES (:id, :id, 'Campus anterior', 0, 0, now(), now())"
            ), {"id": key})
            connection.execute(text(
                "INSERT INTO campus_path_nodes (id, tenant_id, campus_id, lat, lng, created_at, updated_at) "
                "VALUES (:id, :id, :id, 0, 0, now(), now())"
            ), {"id": key})
            connection.execute(text(
                "INSERT INTO campus_buildings "
                "(id, tenant_id, campus_id, name, entrance_lat, entrance_lng, entrance_node_id, created_at, updated_at) "
                "VALUES (:id, :id, :id, 'Bloco anterior', 0, 0, :id, now(), now())"
            ), {"id": key})
            connection.execute(text(
                "INSERT INTO campus_spaces "
                "(id, tenant_id, campus_id, building_id, name, created_at, updated_at) "
                "VALUES (:id, :id, :id, :id, 'Sala anterior', now(), now())"
            ), {"id": key})
            command.upgrade(config, "head")
            building = connection.execute(text(
                "SELECT name, entrance_node_id, public_code FROM campus_buildings WHERE id=:id"
            ), {"id": key}).one()
            space = connection.execute(text(
                "SELECT name, building_id, public_code FROM campus_spaces WHERE id=:id"
            ), {"id": key}).one()
            assert building[:2] == ("Bloco anterior", key)
            assert space[:2] == ("Sala anterior", key)
            assert len(building.public_code) == len(space.public_code) == 36
            assert building.public_code != space.public_code
            assert connection.execute(text("SELECT count(*) FROM campus_path_nodes WHERE id=:id"),
                                      {"id": key}).scalar_one() == 1
            connection.execute(text("UPDATE campus_buildings SET name='Bloco editado' WHERE id=:id"), {"id": key})
            assert connection.execute(text("SELECT public_code FROM campus_buildings WHERE id=:id"),
                                      {"id": key}).scalar_one() == building.public_code
        finally:
            transaction.rollback()


def test_photos_require_one_place_in_same_tenant_and_cascade_on_delete(postgres_engine: Engine) -> None:
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from app.database import Campus, CampusBuilding, CampusPlacePhoto, CampusSpace

    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection)
        try:
            tenant = str(uuid4())
            campus = Campus(tenant_id=tenant, name="Campus", center_lat=0, center_lng=0)
            session.add(campus)
            session.flush()
            building = CampusBuilding(tenant_id=tenant, campus_id=campus.id, name="Bloco", entrance_lat=0, entrance_lng=0)
            session.add(building)
            session.flush()
            space = CampusSpace(tenant_id=tenant, campus_id=campus.id, building_id=building.id, name="Sala")
            session.add(space)
            session.flush()
            values = {"tenant_id": tenant, "campus_id": campus.id, "mime_type": "image/jpeg",
                      "sha256": "a" * 64, "size_bytes": 1, "content": b"x", "sort_order": 0}
            photo = CampusPlacePhoto(space_id=space.id, **values)
            session.add(photo)
            session.flush()
            photo_id = photo.id
            for changes in ({"space_id": space.id, "tenant_id": "other"},
                            {"building_id": building.id, "space_id": space.id}, {}):
                with pytest.raises(IntegrityError), session.begin_nested():
                    session.add(CampusPlacePhoto(**{**values, "sha256": str(uuid4()), **changes}))
                    session.flush()
            session.delete(space)
            session.flush()
            session.expire_all()
            assert session.query(CampusPlacePhoto).filter_by(id=photo_id).count() == 0
        finally:
            session.close()
            transaction.rollback()


def test_new_visual_tables_are_inaccessible_to_direct_public_clients(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT c.relname, r.rolname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN pg_roles r "
            "WHERE n.nspname='public' AND c.relname IN ('campus_landmarks','campus_place_photos') "
            "AND r.rolname IN ('anon','authenticated') "
            "AND has_table_privilege(r.oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')"
        )).all()
    assert rows == []
