"""Retirada do recurso substituído e isolamento da nova revisão Alembic."""

from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text


def _revision():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0023_retire_schematic_locations.py"
    spec = spec_from_file_location("retirement_revision", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_current_map_endpoints_are_exposed(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/campuses" in paths
    assert "/public/{public_slug}/geo-campus" in paths
    assert not any(path.startswith("/locations") or path.endswith("/locations") for path in paths)
    for path in ["/locations", "/locations/retired", "/public/test/locations"]:
        assert client.get(path).status_code == 404
    assert client.post("/locations", json={}).status_code == 404


def test_retirement_drops_only_its_table_in_disposable_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE campus_locations (id TEXT PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE campuses (id TEXT PRIMARY KEY)"))
            connection.execute(text("INSERT INTO campuses VALUES ('synthetic-campus')"))
            with Operations.context(MigrationContext.configure(connection)):
                _revision().upgrade()
            assert not inspect(connection).has_table("campus_locations")
            assert connection.execute(text("SELECT id FROM campuses")).scalar_one() == "synthetic-campus"
    finally:
        engine.dispose()


def test_downgrade_sql_restores_structure_and_protections_without_data() -> None:
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    revision = _revision()
    assert revision.down_revision == "0022"
    with Operations.context(context):
        revision.downgrade()
    sql = output.getvalue()
    assert "CREATE TABLE campus_locations" in sql
    assert "ck_campus_locations_x_range" in sql
    assert "ix_campus_locations_tenant_active_name" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FROM anon" in sql and "FROM authenticated" in sql
    assert "INSERT INTO" not in sql
