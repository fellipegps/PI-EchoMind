"""Verifica integridade e RLS do mapa geográfico no PostgreSQL descartável."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


pytestmark = pytest.mark.integration

GEO_TABLES = (
    "campuses", "campus_buildings", "campus_spaces",
    "campus_path_nodes", "campus_path_edges",
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
            "'campus_path_nodes', 'campus_path_edges')"
        )).all())
    assert enabled == {table: True for table in GEO_TABLES}

    for table in GEO_TABLES[1:]:
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
