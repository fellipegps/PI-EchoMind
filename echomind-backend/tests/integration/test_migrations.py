"""Smoke tests do head Alembic em PostgreSQL 17 com pgvector real."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_POSTGRES_MAJOR = 17
EXPECTED_TABLES = {
    "alembic_version",
    "config",
    "document_chunks",
    "document_chunk_parents",
    "documents",
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


def test_document_tables_columns_indexes_and_constraints(postgres_engine: Engine) -> None:
    inspector = inspect(postgres_engine)
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    chunk_columns = {column["name"] for column in inspector.get_columns("document_chunks")}
    parent_columns = {
        column["name"] for column in inspector.get_columns("document_chunk_parents")
    }

    assert document_columns == {
        "id",
        "tenant_id",
        "filename",
        "mime_type",
        "size_bytes",
        "sha256",
        "status",
        "chunk_count",
        "document_type",
        "document_number",
        "department",
        "published_at",
        "valid_until",
        "error_message",
        "created_at",
        "updated_at",
        "processed_at",
    }
    assert chunk_columns == {
        "id",
        "tenant_id",
        "document_id",
        "parent_id",
        "chunk_index",
        "content",
        "page_start",
        "page_end",
        "section_title",
        "created_at",
    }
    assert parent_columns == {
        "id",
        "tenant_id",
        "document_id",
        "parent_index",
        "content",
        "page_start",
        "page_end",
        "section_title",
        "created_at",
    }
    assert "embedding" not in document_columns | chunk_columns

    document_indexes = {index["name"] for index in inspector.get_indexes("documents")}
    chunk_indexes = {index["name"] for index in inspector.get_indexes("document_chunks")}
    parent_indexes = {
        index["name"] for index in inspector.get_indexes("document_chunk_parents")
    }
    assert {
        "ix_documents_tenant_id",
        "ix_documents_tenant_status",
        "ix_documents_tenant_sha256",
        "ix_documents_tenant_created_at",
    } <= document_indexes
    assert {
        "ix_document_chunks_tenant_id",
        "ix_document_chunks_document_id",
        "ix_document_chunks_parent_id",
    } <= chunk_indexes
    assert {
        "ix_document_chunk_parents_tenant_id",
        "ix_document_chunk_parents_document_id",
        "ix_document_chunk_parents_tenant_document",
    } <= parent_indexes
    with postgres_engine.connect() as connection:
        fts_indexes = set(
            connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
                    "AND indexname LIKE '%_fts_portuguese'"
                )
            ).scalars()
        )
    assert {
        "ix_faqs_fts_portuguese",
        "ix_events_fts_portuguese",
        "ix_documents_fts_portuguese",
        "ix_document_chunks_fts_portuguese",
    } <= fts_indexes

    document_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("documents")
    }
    chunk_checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("document_chunks")
    }
    parent_checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("document_chunk_parents")
    }
    assert {
        "ck_documents_status",
        "ck_documents_size_bytes_positive",
        "ck_documents_sha256_length",
        "ck_documents_chunk_count_nonnegative",
    } <= document_checks
    assert {
        "ck_document_chunks_chunk_index_nonnegative",
        "ck_document_chunks_page_start_positive",
        "ck_document_chunks_page_end_positive",
        "ck_document_chunks_page_range",
    } <= chunk_checks
    assert {
        "ck_document_chunk_parents_parent_index_nonnegative",
        "ck_document_chunk_parents_page_start_positive",
        "ck_document_chunk_parents_page_end_positive",
        "ck_document_chunk_parents_page_range",
    } <= parent_checks

    unique_constraints = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("document_chunks")
    }
    assert unique_constraints["uq_document_chunks_document_id_chunk_index"] == [
        "document_id",
        "chunk_index",
    ]

    foreign_keys = {
        foreign_key["name"]: foreign_key
        for foreign_key in inspector.get_foreign_keys("document_chunks")
    }
    document_fk = foreign_keys["fk_document_chunks_document_id_documents"]
    assert document_fk["constrained_columns"] == ["document_id"]
    assert document_fk["referred_table"] == "documents"
    assert document_fk["referred_columns"] == ["id"]
    assert document_fk["options"]["ondelete"] == "CASCADE"
    parent_fk = foreign_keys["fk_document_chunks_parent_id_document_chunk_parents"]
    assert parent_fk["constrained_columns"] == ["parent_id"]
    assert parent_fk["referred_table"] == "document_chunk_parents"
    assert parent_fk["referred_columns"] == ["id"]
    assert parent_fk["options"]["ondelete"] == "SET NULL"

    parent_foreign_keys = inspector.get_foreign_keys("document_chunk_parents")
    assert len(parent_foreign_keys) == 1
    assert parent_foreign_keys[0]["constrained_columns"] == ["document_id"]
    assert parent_foreign_keys[0]["referred_table"] == "documents"
    assert parent_foreign_keys[0]["options"]["ondelete"] == "CASCADE"


def test_document_defaults_constraints_uniqueness_and_cascade(postgres_engine: Engine) -> None:
    document_values = {
        "id": "doc-migration-test",
        "tenant_id": "tenant-a",
        "filename": "regulamento.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 128,
        "sha256": "a" * 64,
    }

    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id, tenant_id, filename, mime_type, size_bytes, sha256
                ) VALUES (
                    :id, :tenant_id, :filename, :mime_type, :size_bytes, :sha256
                )
                """
            ),
            document_values,
        )
        persisted = connection.execute(
            text(
                """
                SELECT status, chunk_count, created_at, updated_at,
                       processed_at, error_message, valid_until
                FROM documents
                WHERE id = :id
                """
            ),
            {"id": document_values["id"]},
        ).mappings().one()
        connection.execute(
            text(
                """
                INSERT INTO document_chunks (
                    id, tenant_id, document_id, chunk_index, content
                ) VALUES (
                    'chunk-migration-test', 'tenant-a', :document_id, 0, 'conteudo'
                )
                """
            ),
            {"document_id": document_values["id"]},
        )

    assert persisted["status"] == "pending"
    assert persisted["chunk_count"] == 0
    assert persisted["created_at"] is not None
    assert persisted["updated_at"] is not None
    assert persisted["processed_at"] is None
    assert persisted["error_message"] is None
    assert persisted["valid_until"] is None

    with pytest.raises(IntegrityError):
        with postgres_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id, tenant_id, document_id, chunk_index, content
                    ) VALUES (
                        'chunk-duplicate', 'tenant-a', :document_id, 0, 'duplicado'
                    )
                    """
                ),
                {"document_id": document_values["id"]},
            )

    with pytest.raises(IntegrityError):
        with postgres_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO documents (
                        id, tenant_id, filename, mime_type, size_bytes, sha256, status
                    ) VALUES (
                        'doc-invalid-status', 'tenant-a', 'invalido.txt', 'text/plain',
                        1, :sha256, 'unknown'
                    )
                    """
                ),
                {"sha256": "b" * 64},
            )

    with pytest.raises(IntegrityError):
        with postgres_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id, tenant_id, document_id, chunk_index, content
                    ) VALUES (
                        'chunk-orphan', 'tenant-a', 'missing-document', 0, 'orfao'
                    )
                    """
                )
            )

    with postgres_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM documents WHERE id = :id"),
            {"id": document_values["id"]},
        )
        remaining_chunks = connection.execute(
            text("SELECT count(*) FROM document_chunks WHERE document_id = :id"),
            {"id": document_values["id"]},
        ).scalar_one()

    assert remaining_chunks == 0


def test_document_tables_follow_existing_rls_pattern(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        rls_rows = connection.execute(
            text(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                       count(p.policyname) AS policy_count
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_policies p
                  ON p.schemaname = n.nspname
                 AND p.tablename = c.relname
                WHERE n.nspname = 'public'
                  AND c.relname IN ('documents', 'document_chunks', 'document_chunk_parents')
                GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity
                ORDER BY c.relname
                """
            )
        ).mappings().all()

    assert [row["relname"] for row in rls_rows] == [
        "document_chunk_parents",
        "document_chunks",
        "documents",
    ]
    assert all(row["relrowsecurity"] for row in rls_rows)
    assert not any(row["relforcerowsecurity"] for row in rls_rows)
    assert all(row["policy_count"] == 0 for row in rls_rows)
