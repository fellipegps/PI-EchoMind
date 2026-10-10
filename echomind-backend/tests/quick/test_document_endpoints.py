"""Contratos HTTP administrativos de consulta e exclusao documental."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _create_document(
    db,
    *,
    tenant_id: str = "test-admin",
    filename: str = "norma.txt",
    status: str = "ready",
    created_at: datetime | None = None,
    chunk_contents: tuple[str, ...] = (),
):
    from app.document_repository import (
        DocumentChunkData,
        DocumentCreateData,
        create_document,
        replace_document_chunks,
        transition_document_status,
    )

    digest = sha256(f"{tenant_id}:{filename}:{uuid4()}".encode()).hexdigest()
    document = create_document(
        db,
        tenant_id=tenant_id,
        data=DocumentCreateData(
            filename=filename,
            mime_type="text/plain",
            size_bytes=64,
            sha256=digest,
        ),
    )
    if status != "pending":
        document = transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="processing",
        )
    if status == "ready":
        document = transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="ready",
        )
    elif status == "error":
        document = transition_document_status(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="error",
            error_message="Falha sintetica.",
        )
    elif status not in {"pending", "processing"}:
        raise ValueError(f"Status sintetico invalido: {status}")

    if chunk_contents:
        replace_document_chunks(
            db,
            tenant_id=tenant_id,
            document_id=document.id,
            chunks=[DocumentChunkData(content=content) for content in chunk_contents],
        )
    if created_at is not None:
        document.created_at = created_at
    db.commit()
    return document


def _request_without_auth(client, quick_test_context, request):
    app = quick_test_context.app
    auth_dependency = quick_test_context.get_current_user
    override = app.dependency_overrides.pop(auth_dependency)
    try:
        return request()
    finally:
        app.dependency_overrides[auth_dependency] = override


def test_documents_requires_authentication(client: TestClient, quick_test_context) -> None:
    response = _request_without_auth(
        client,
        quick_test_context,
        lambda: client.get("/documents"),
    )

    assert response.status_code == 403


def test_documents_rejects_invalid_authentication(
    client: TestClient,
    quick_test_context,
    monkeypatch,
) -> None:
    from app import auth

    monkeypatch.setattr(
        auth.supabase.auth,
        "get_user",
        MagicMock(side_effect=RuntimeError("token invalido")),
    )
    response = _request_without_auth(
        client,
        quick_test_context,
        lambda: client.get(
            "/documents",
            headers={"Authorization": "Bearer token-invalido"},
        ),
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_list_documents_empty(client: TestClient) -> None:
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json() == {"documents": [], "total": 0}


def test_list_documents_is_ordered_and_tenant_scoped(client: TestClient, db) -> None:
    older = _create_document(
        db,
        filename="antigo.txt",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = _create_document(
        db,
        filename="recente.txt",
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    _create_document(
        db,
        tenant_id="outro-tenant",
        filename="sigiloso.txt",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    response = client.get("/documents", params={"tenant_id": "outro-tenant"})

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [item["id"] for item in response.json()["documents"]] == [
        newer.id,
        older.id,
    ]
    assert all("tenant_id" not in item for item in response.json()["documents"])


def test_get_document_returns_own_document(client: TestClient, db) -> None:
    document = _create_document(db, filename="proprio.txt")

    response = client.get(f"/documents/{document.id}")

    assert response.status_code == 200
    assert response.json()["id"] == document.id
    assert response.json()["filename"] == "proprio.txt"
    assert response.json()["status"] == "ready"
    assert "tenant_id" not in response.json()


def test_get_cross_tenant_matches_not_found(client: TestClient, db) -> None:
    foreign = _create_document(db, tenant_id="outro-tenant")

    foreign_response = client.get(f"/documents/{foreign.id}")
    missing_response = client.get("/documents/documento-inexistente")

    assert foreign_response.status_code == 404
    assert foreign_response.json() == missing_response.json()


def test_delete_document_removes_vectors_chunks_and_record(
    client: TestClient,
    db,
    fake_rag_engine,
) -> None:
    from app.document_repository import get_document, list_document_chunks

    document = _create_document(
        db,
        chunk_contents=("Primeiro chunk.", "Segundo chunk."),
    )
    chunk_ids = tuple(
        chunk.id
        for chunk in list_document_chunks(
            db,
            tenant_id="test-admin",
            document_id=document.id,
        )
    )

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code == 204
    assert response.content == b""
    assert fake_rag_engine.deleted_document_chunks == [(document.id, chunk_ids)]
    assert get_document(db, tenant_id="test-admin", document_id=document.id) is None
    assert list_document_chunks(
        db,
        tenant_id="test-admin",
        document_id=document.id,
    ) == []


def test_delete_cross_tenant_returns_same_404(
    client: TestClient,
    db,
    fake_rag_engine,
) -> None:
    from app.document_repository import get_document

    foreign = _create_document(db, tenant_id="outro-tenant")

    response = client.delete(f"/documents/{foreign.id}")

    assert response.status_code == 404
    assert fake_rag_engine.deleted_document_chunks == []
    assert get_document(db, tenant_id="outro-tenant", document_id=foreign.id) is not None


@pytest.mark.parametrize("status", ["pending", "processing"])
def test_delete_pending_or_processing_returns_conflict(
    client: TestClient,
    db,
    fake_rag_engine,
    status: str,
) -> None:
    from app.document_repository import get_document

    document = _create_document(db, status=status)

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code == 409
    assert fake_rag_engine.deleted_document_chunks == []
    assert get_document(db, tenant_id="test-admin", document_id=document.id) is not None


def test_vector_failure_preserves_relational_state(
    durable_delete_api,
    fake_rag_engine,
) -> None:
    from sqlalchemy.orm import Session
    from app.document_repository import get_document, list_document_chunks

    client, engine = durable_delete_api
    with Session(engine) as session:
        document = _create_document(session, chunk_contents=("Chunk preservado.",))
        identifier = document.id
    fake_rag_engine.document_chunk_delete_error = True

    response = client.delete(f"/documents/{identifier}")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Não foi possível excluir os vetores do documento."
    }
    with Session(engine) as session:
        restored = get_document(session, tenant_id="test-admin", document_id=identifier)
        assert restored.status == "ready"
        assert restored.error_message is None
        assert len(list_document_chunks(
            session, tenant_id="test-admin", document_id=identifier,
        )) == 1


@pytest.fixture()
def durable_delete_api(quick_test_context, fake_rag_engine):
    """SQLite independente: commits/rollbacks reais, sem transacao externa."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import Session
    from sqlalchemy.pool import StaticPool
    from app.database import Base
    from app import main

    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(engine)

    def request_db():
        with Session(engine) as session:
            yield session

    app = quick_test_context.app
    overrides = dict(app.dependency_overrides)
    app.dependency_overrides[quick_test_context.get_db] = request_db
    app.dependency_overrides[quick_test_context.get_current_user] = lambda: quick_test_context.current_user_type(
        id="test-admin", email="delete@example.test", is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[main.get_document_rag] = lambda: fake_rag_engine
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)
        engine.dispose()


@pytest.mark.parametrize(
    ("failure", "expected_http", "expected_status"),
    [
        ("relational", 500, "ready"),
        ("commit", 500, "ready"),
        ("compensation", 503, "error"),
        ("recovery-commit", 503, "error"),
        ("prepare", 500, "ready"),
        ("already-error", 500, "error"),
    ],
)
def test_delete_compensation_and_retry(
    durable_delete_api, fake_rag_engine, monkeypatch,
    failure, expected_http, expected_status,
):
    from sqlalchemy.orm import Session
    from app import main
    from app.document_repository import get_document, list_document_chunks

    client, engine = durable_delete_api
    with Session(engine) as session:
        document = _create_document(
            session, status="error" if failure == "already-error" else "ready",
            chunk_contents=("Primeiro trecho.", "Segundo trecho."),
        )
        identifier = document.id
        chunk_ids = [chunk.id for chunk in list_document_chunks(
            session, tenant_id="test-admin", document_id=identifier,
        )]
    original_delete = main.delete_document_record
    original_commit = Session.commit
    failed = False
    original_reindex = fake_rag_engine.reindex_document_chunks

    def fail_relational(*args, **kwargs):
        if failure in {"relational", "compensation", "already-error"}:
            raise RuntimeError("Falha relacional sintetica.")
        return original_delete(*args, **kwargs)

    def fail_commit(session):
        nonlocal failed
        vectors_removed = bool(fake_rag_engine.deleted_document_chunks)
        if failure == "prepare" or (
            failure in {"commit", "recovery-commit"} and vectors_removed
            and (not failed or failure == "recovery-commit")
        ):
            failed = True
            raise RuntimeError("Falha sintetica de commit.")
        return original_commit(session)

    monkeypatch.setattr(main, "delete_document_record", fail_relational)
    monkeypatch.setattr(Session, "commit", fail_commit)
    fake_rag_engine.document_chunk_reindex_error = failure == "compensation"
    response = client.delete(f"/documents/{identifier}")
    assert response.status_code == expected_http
    with Session(engine) as session:
        stored = get_document(session, tenant_id="test-admin", document_id=identifier)
        assert stored.status == expected_status
        assert [chunk.id for chunk in list_document_chunks(
            session, tenant_id="test-admin", document_id=identifier,
        )] == chunk_ids
        if expected_status == "error":
            assert "Exclusão não concluída" in stored.error_message
        else:
            assert stored.error_message is None
    if failure == "prepare":
        assert fake_rag_engine.deleted_document_chunks == []
    elif failure != "already-error":
        assert fake_rag_engine.deleted_document_chunks == [(identifier, tuple(chunk_ids))]
    if failure in {"relational", "commit", "recovery-commit"}:
        assert fake_rag_engine.reindexed_document_chunks == [(identifier, tuple(chunk_ids))]
    if failure == "already-error":
        assert fake_rag_engine.reindexed_document_chunks == []
        with Session(engine) as session:
            recovery_message = get_document(
                session, tenant_id="test-admin", document_id=identifier,
            ).error_message
        assert client.delete(f"/documents/{identifier}").status_code == 500
        with Session(engine) as session:
            assert get_document(
                session, tenant_id="test-admin", document_id=identifier,
            ).error_message == recovery_message

    monkeypatch.setattr(Session, "commit", original_commit)
    monkeypatch.setattr(main, "delete_document_record", original_delete)
    monkeypatch.setattr(fake_rag_engine, "reindex_document_chunks", original_reindex)
    fake_rag_engine.document_chunk_reindex_error = False
    assert client.delete(f"/documents/{identifier}").status_code == 204
    assert client.delete(f"/documents/{identifier}").status_code == 404
    with Session(engine) as session:
        assert get_document(session, tenant_id="test-admin", document_id=identifier) is None
        assert list_document_chunks(session, tenant_id="test-admin", document_id=identifier) == []
