"""Deduplicacao atomica e migrations em PostgreSQL descartavel real."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[2]
INDEX_NAME = "uq_documents_active_tenant_sha256"
ACTIVE_STATUSES = ("pending", "processing", "ready")


@pytest.fixture()
def tenant(postgres_engine):
    tenant_id = f"dedup-{uuid4()}"
    yield tenant_id
    from app.database import Document

    with postgres_engine.begin() as connection:
        connection.execute(delete(Document).where(Document.tenant_id.in_([tenant_id, tenant_id + "-other"])))


def _row(tenant_id, *, status="pending", digest="a" * 64, size=5):
    from app.database import Document

    return Document(
        tenant_id=tenant_id, filename="dedup.txt", mime_type="text/plain",
        size_bytes=size, sha256=digest, status=status,
    )


@pytest.mark.parametrize("original_status", ACTIVE_STATUSES)
@pytest.mark.parametrize("new_status", ACTIVE_STATUSES)
def test_database_rejects_every_active_status_pair(postgres_engine, tenant, original_status, new_status):
    with Session(postgres_engine) as session:
        session.add(_row(tenant, status=original_status))
        session.commit()
    with Session(postgres_engine) as session:
        session.add(_row(tenant, status=new_status))
        with pytest.raises(IntegrityError) as caught:
            session.commit()
        assert caught.value.orig.pgcode == "23505"
        assert caught.value.orig.diag.constraint_name == INDEX_NAME
        session.rollback()


def test_retry_after_error_and_same_hash_in_other_tenant(postgres_engine, tenant):
    from app.document_repository import DocumentCreateData, create_document

    with Session(postgres_engine) as session:
        session.add(_row(tenant, status="error"))
        session.commit()
        for tenant_id in (tenant, tenant + "-other"):
            create_document(session, tenant_id=tenant_id, data=DocumentCreateData(
                filename="retry.txt", mime_type="text/plain", size_bytes=5, sha256="a" * 64,
            ))
            session.commit()
        assert session.execute(text("SELECT count(*) FROM documents WHERE tenant_id = :tenant"), {"tenant": tenant}).scalar_one() == 2


def test_database_rejects_reactivating_error_when_hash_is_active(postgres_engine, tenant):
    with Session(postgres_engine) as session:
        failed = _row(tenant, status="error")
        session.add_all([failed, _row(tenant)])
        session.commit()
        failed.status = "pending"
        with pytest.raises(IntegrityError) as caught:
            session.commit()
        assert caught.value.orig.diag.constraint_name == INDEX_NAME
        session.rollback()
        assert failed.status == "error"


def test_two_independent_sessions_cannot_commit_same_hash(postgres_engine, tenant, monkeypatch):
    from app import document_repository as repository
    from app.database import Document

    barrier = Barrier(2, timeout=15)
    original = repository.find_active_duplicate_document

    def both_read_before_insert(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result is None
        barrier.wait()
        return result

    monkeypatch.setattr(repository, "find_active_duplicate_document", both_read_before_insert)

    def upload(_):
        with Session(postgres_engine) as session:
            pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            try:
                document = repository.create_document(session, tenant_id=tenant, data=repository.DocumentCreateData(
                    filename="race.txt", mime_type="text/plain", size_bytes=5, sha256="a" * 64,
                ))
                session.commit()
                return pid, "created", document.id
            except repository.DuplicateDocumentError:
                session.rollback()
                return pid, "duplicate", None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(upload, range(2)))
    assert len({result[0] for result in results}) == 2
    assert sorted(result[1] for result in results) == ["created", "duplicate"]
    with Session(postgres_engine) as session:
        assert session.query(Document).filter_by(tenant_id=tenant).count() == 1


@pytest.fixture()
def upload_api(postgres_engine, tenant, monkeypatch):
    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.database import get_db

    def independent_db():
        with Session(postgres_engine) as session:
            yield session

    scheduled = []
    monkeypatch.setattr(main, "process_document", lambda **kwargs: scheduled.append(kwargs))
    overrides = dict(main.app.dependency_overrides)
    main.app.dependency_overrides[get_db] = independent_db
    main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=tenant, email="dedup@example.test", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    main.app.dependency_overrides[main.enforce_upload_rate_limit] = lambda: None
    try:
        yield main, scheduled
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(overrides)


def _post_upload(app):
    # Um portal/event loop por requisicao: o endpoint usa SQLAlchemy sincrono.
    with TestClient(app) as client:
        return client.post("/documents/upload", files={"file": ("dedup.txt", b"dedup", "text/plain")})


def test_concurrent_upload_returns_202_and_409_and_schedules_only_winner(upload_api, tenant, monkeypatch):
    from app import document_repository as repository

    main, scheduled = upload_api
    barrier = Barrier(2, timeout=15)
    original_find = repository.find_active_duplicate_document
    def both_read_before_insert(*args, **kwargs):
        result = original_find(*args, **kwargs)
        assert result is None
        barrier.wait()
        return result

    monkeypatch.setattr(repository, "find_active_duplicate_document", both_read_before_insert)
    # Ambas as validacoes preliminares e os dois checks no repository passam.
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: _post_upload(main.app), range(2)))
    assert sorted(response.status_code for response in responses) == [202, 409]
    winner = next(response.json() for response in responses if response.status_code == 202)
    assert len(scheduled) == 1
    assert scheduled[0] == {"document_id": winner["id"], "tenant_id": tenant, "content": b"dedup"}

    # A repeticao sequencial tambem nao agenda trabalho.
    monkeypatch.setattr(repository, "find_active_duplicate_document", original_find)
    assert _post_upload(main.app).status_code == 409
    assert len(scheduled) == 1


@pytest.mark.parametrize("failure", ["check", "primary-key"])
def test_other_integrity_errors_remain_500_without_scheduling(upload_api, postgres_engine, tenant, monkeypatch, failure):
    main, scheduled = upload_api
    from app.database import Document
    from app.document_repository import create_document

    existing_id = None
    if failure == "primary-key":
        with Session(postgres_engine) as session:
            existing = _row(tenant, digest="b" * 64)
            session.add(existing)
            session.commit()
            existing_id = existing.id

    def broken_create(session, **kwargs):
        if failure == "check":
            from dataclasses import replace
            kwargs["data"] = replace(kwargs["data"], size_bytes=0)
            return create_document(session, **kwargs)
        document = _row(tenant, digest=sha256(b"dedup").hexdigest())
        document.id = existing_id
        session.add(document)
        session.flush()

    monkeypatch.setattr(main, "create_document", broken_create)
    assert _post_upload(main.app).status_code == 500
    assert scheduled == []
    with Session(postgres_engine) as session:
        assert session.query(Document).filter_by(tenant_id=tenant).count() == (1 if existing_id else 0)


@pytest.fixture()
def migration_database(postgres_engine):
    # A engine ja foi validada pelo conftest como banco LOCAL descartavel.
    name = "echomind_dedup_" + uuid4().hex
    quoted_name = postgres_engine.dialect.identifier_preparer.quote(name)
    with postgres_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
    url = postgres_engine.url.set(database=name)
    engine = create_engine(url, poolclass=NullPool)
    env = {**os.environ, "DATABASE_URL": url.render_as_string(hide_password=False), "RAG_WARMUP_ENABLED": "false"}

    def migrate(*args, success=True):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=BACKEND_ROOT,
            env=env, capture_output=True, text=True, timeout=60,
        )
        assert (result.returncode == 0) is success, result.stdout + result.stderr
        return result.stdout + result.stderr

    try:
        yield engine, migrate
    finally:
        engine.dispose()
        with postgres_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f"DROP DATABASE {quoted_name} WITH (FORCE)")


@pytest.mark.parametrize("starting_revision", ["base", "0021"])
def test_migration_from_zero_and_previous_head(migration_database, starting_revision):
    engine, migrate = migration_database
    if starting_revision == "0021":
        migrate("upgrade", "0021")
        with Session(engine) as session:
            session.add_all([_row("migration", status="error"), _row("migration"), _row("other")])
            session.commit()
    migrate("upgrade", "head")
    index = next(index for index in inspect(engine).get_indexes("documents") if index["name"] == INDEX_NAME)
    assert index["unique"] is True
    assert index["column_names"] == ["tenant_id", "sha256"]
    assert all(status in str(index["dialect_options"]["postgresql_where"]) for status in ACTIVE_STATUSES)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0022"
        if starting_revision == "0021":
            assert connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 3
    migrate("downgrade", "0021")
    assert INDEX_NAME not in {index["name"] for index in inspect(engine).get_indexes("documents")}
    migrate("upgrade", "head")


def test_migration_blocks_existing_duplicates_without_deleting(migration_database):
    engine, migrate = migration_database
    migrate("upgrade", "0021")
    with Session(engine) as session:
        session.add_all([_row("conflicting-tenant", status=status) for status in ACTIVE_STATUSES])
        session.add(_row("conflicting-tenant", status="error"))
        session.commit()
    output = migrate("upgrade", "head", success=False)
    assert "Documentos ativos duplicados" in output
    assert "conflicting-tenant" in output
    assert "a" * 64 in output
    assert "Nenhum registro foi removido" in output
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0021"
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 4
    assert INDEX_NAME not in {index["name"] for index in inspect(engine).get_indexes("documents")}
