"""Smoke tests do head Alembic em PostgreSQL 17 com pgvector real."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_POSTGRES_MAJOR = 17
EXPECTED_TABLES = {
    "alembic_version",
    "config",
    "events",
    "faqs",
    "interactions",
    "unanswered_questions",
}


def test_postgresql_major_and_vector_extension(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        server_version_num = int(connection.execute(text("SHOW server_version_num")).scalar_one())
        vector_version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()

    assert server_version_num // 10_000 == EXPECTED_POSTGRES_MAJOR
    assert vector_version is not None


def test_database_revision_is_exactly_alembic_head(postgres_engine: Engine) -> None:
    alembic_config = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()

    with postgres_engine.connect() as connection:
        applied_revisions = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all()

    assert applied_revisions == [expected_head]

    existing_tables = set(inspect(postgres_engine).get_table_names(schema="public"))
    assert EXPECTED_TABLES <= existing_tables


def test_pgvector_executes_real_vector_operation(postgres_engine: Engine) -> None:
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TEMP TABLE pgvector_smoke "
                "(embedding vector(3) NOT NULL) ON COMMIT DROP"
            )
        )
        connection.execute(
            text("INSERT INTO pgvector_smoke (embedding) VALUES ('[1,2,3]'::vector)")
        )
        distance = connection.execute(
            text(
                "SELECT embedding <-> '[1,2,4]'::vector "
                "FROM pgvector_smoke"
            )
        ).scalar_one()

    assert distance == pytest.approx(1.0)
