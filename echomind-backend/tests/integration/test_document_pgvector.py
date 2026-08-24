"""Ciclo documental no PGVector real com embeddings locais deterministicos."""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


def _document(document_id: str, tenant_id: str, filename: str):
    return SimpleNamespace(
        id=document_id,
        tenant_id=tenant_id,
        filename=filename,
        mime_type="application/pdf",
        document_type="regulamento",
        document_number="42/2026",
        department="Secretaria Academica",
        published_at=date(2026, 2, 1),
        valid_until=date(2027, 2, 1),
    )


def _chunk(chunk_id: str, document_id: str, tenant_id: str, index: int, content: str):
    return SimpleNamespace(
        id=chunk_id,
        tenant_id=tenant_id,
        document_id=document_id,
        chunk_index=index,
        content=content,
        page_start=index + 1,
        page_end=index + 1,
        section_title=f"Secao {index + 1}",
    )


@pytest.fixture()
def real_rag_runtime(
    monkeypatch,
    integration_database_url,
    deterministic_fake_embeddings,
):
    from app import rag_engine

    monkeypatch.setattr(rag_engine, "DATABASE_URL", integration_database_url)
    monkeypatch.setattr(
        rag_engine,
        "_get_embeddings",
        lambda: deterministic_fake_embeddings,
    )
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()
    tenant_ids: set[str] = set()

    def make_indexer(tenant_id: str):
        tenant_ids.add(tenant_id)
        indexer = object.__new__(rag_engine.RAGEngine)
        indexer.tenant_id = tenant_id
        return indexer

    yield SimpleNamespace(module=rag_engine, make_indexer=make_indexer)

    for tenant_id in tenant_ids:
        rag_engine._get_vector_store(tenant_id).delete_collection()
    rag_engine._get_vector_store.cache_clear()
    rag_engine._enable_langchain_rls_if_possible.cache_clear()


def _documents_for(runtime, tenant_id: str):
    store = runtime.module._get_vector_store(tenant_id)
    return store.similarity_search("consulta sintetica", k=20)


def _create_pending_processing_document(tenant_id: str) -> str:
    from app.database import SessionLocal
    from app.document_repository import DocumentCreateData, create_document

    session = SessionLocal()
    try:
        document = create_document(
            session,
            tenant_id=tenant_id,
            data=DocumentCreateData(
                filename="norma.txt",
                mime_type="text/plain",
                size_bytes=128,
                sha256=sha256(f"{tenant_id}:{uuid4()}".encode()).hexdigest(),
            ),
        )
        document_id = document.id
        session.commit()
        return document_id
    finally:
        session.close()


def _processing_state(tenant_id: str, document_id: str):
    from app.database import SessionLocal
    from app.document_repository import get_document, list_document_chunks

    session = SessionLocal()
    try:
        document = get_document(session, tenant_id=tenant_id, document_id=document_id)
        chunks = list_document_chunks(
            session,
            tenant_id=tenant_id,
            document_id=document_id,
        )
        return SimpleNamespace(
            status=document.status,
            chunk_count=document.chunk_count,
            processed_at=document.processed_at,
            error_message=document.error_message,
            chunk_contents=[chunk.content for chunk in chunks],
        )
    finally:
        session.close()


def _remove_processing_document(tenant_id: str, document_id: str) -> None:
    from app.database import SessionLocal
    from app.document_repository import delete_document

    session = SessionLocal()
    try:
        delete_document(session, tenant_id=tenant_id, document_id=document_id)
        session.commit()
    finally:
        session.close()


def _create_ready_document_with_vector(runtime, tenant_id: str) -> str:
    from app.database import SessionLocal
    from app.document_repository import (
        DocumentChunkData,
        DocumentCreateData,
        create_document,
        replace_document_chunks,
        transition_document_status,
    )

    session = SessionLocal()
    try:
        document = create_document(
            session,
            tenant_id=tenant_id,
            data=DocumentCreateData(
                filename="api-delete.txt",
                mime_type="text/plain",
                size_bytes=96,
                sha256=sha256(f"{tenant_id}:{uuid4()}".encode()).hexdigest(),
            ),
        )
        transition_document_status(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="processing",
        )
        document = transition_document_status(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            target_status="ready",
        )
        chunks = replace_document_chunks(
            session,
            tenant_id=tenant_id,
            document_id=document.id,
            chunks=(DocumentChunkData(content="Chunk sintetico da API."),),
        )
        session.commit()
        runtime.make_indexer(tenant_id).index_document_chunk(document, chunks[0])
        return document.id
    finally:
        session.close()


def test_real_pgvector_index_and_reindex_are_idempotent_and_remove_orphans(
    real_rag_runtime,
) -> None:
    tenant_id = "pr12-idempotency"
    indexer = real_rag_runtime.make_indexer(tenant_id)
    document = _document("doc-1", tenant_id, "regulamento.pdf")
    chunk_zero = _chunk("chunk-0", document.id, tenant_id, 0, "Conteudo inicial.")
    orphan = _chunk("chunk-1", document.id, tenant_id, 1, "Conteudo orfao.")

    indexer.index_document_chunk(document, chunk_zero)
    indexer.index_document_chunk(document, chunk_zero)
    assert len(_documents_for(real_rag_runtime, tenant_id)) == 1

    indexer.index_document_chunk(document, orphan)
    updated = _chunk("chunk-0", document.id, tenant_id, 0, "Conteudo atualizado.")
    indexer.reindex_document_chunks(
        document,
        (updated,),
        previous_chunks=(chunk_zero, orphan),
    )

    stored = _documents_for(real_rag_runtime, tenant_id)
    assert len(stored) == 1
    assert stored[0].page_content.endswith("Conteudo atualizado.")
    assert stored[0].metadata["source_type"] == "document_chunk"
    assert stored[0].metadata["source_id"] == "chunk-0"
    assert stored[0].metadata["tenant_id"] == tenant_id
    assert stored[0].metadata["document_id"] == document.id
    assert stored[0].metadata["filename"] == "regulamento.pdf"
    assert stored[0].metadata["page_start"] == 1
    assert stored[0].metadata["page_end"] == 1
    assert stored[0].metadata["chunk_index"] == 0
    assert stored[0].metadata["published_at"] == "2026-02-01"


def test_real_pgvector_deletion_is_scoped_by_document_and_tenant(
    real_rag_runtime,
) -> None:
    tenant_a = "pr12-tenant-a"
    tenant_b = "pr12-tenant-b"
    indexer_a = real_rag_runtime.make_indexer(tenant_a)
    indexer_b = real_rag_runtime.make_indexer(tenant_b)
    document_a = _document("doc-a", tenant_a, "tenant-a.pdf")
    document_a_other = _document("doc-a-other", tenant_a, "outro-a.pdf")
    document_b = _document("doc-b", tenant_b, "tenant-b.pdf")
    chunk_a = _chunk("shared-chunk", document_a.id, tenant_a, 0, "Somente tenant A.")
    chunk_a_second = _chunk("chunk-a-second", document_a.id, tenant_a, 1, "Segundo chunk A.")
    chunk_a_other = _chunk("chunk-a-other", document_a_other.id, tenant_a, 0, "Outro doc A.")
    chunk_b = _chunk("shared-chunk", document_b.id, tenant_b, 0, "Somente tenant B.")

    indexer_a.index_document_chunk(document_a, chunk_a)
    indexer_a.index_document_chunk(document_a, chunk_a_second)
    indexer_a.index_document_chunk(document_a_other, chunk_a_other)
    indexer_b.index_document_chunk(document_b, chunk_b)

    assert {doc.metadata["tenant_id"] for doc in _documents_for(real_rag_runtime, tenant_b)} == {
        tenant_b
    }
    indexer_a.delete_document_chunks(document_a, (chunk_a, chunk_a_second))

    remaining_a = _documents_for(real_rag_runtime, tenant_a)
    remaining_b = _documents_for(real_rag_runtime, tenant_b)
    assert [doc.metadata["document_id"] for doc in remaining_a] == [document_a_other.id]
    assert [doc.metadata["document_id"] for doc in remaining_b] == [document_b.id]


def test_real_pgvector_keeps_faq_and_event_retrievable(real_rag_runtime) -> None:
    tenant_id = "pr12-regression"
    indexer = real_rag_runtime.make_indexer(tenant_id)
    faq = SimpleNamespace(id="faq-1", question="Qual o prazo?", answer="Trinta dias.")
    event = SimpleNamespace(
        id="event-1",
        title="Semana academica",
        event_date="2026-09-03",
        event_type="palestra",
        description="Evento sintetico.",
    )

    indexer.index_faq(faq)
    indexer.index_event(event)

    stored = _documents_for(real_rag_runtime, tenant_id)
    assert {doc.metadata["source_type"] for doc in stored} == {"faq", "event"}
    assert {doc.metadata["source_id"] for doc in stored} == {"faq-1", "event-1"}


def test_process_document_completes_with_real_postgres_and_pgvector(
    real_rag_runtime,
) -> None:
    from app.document_processing import process_document

    tenant_id = "pr13-processing-success"
    real_rag_runtime.make_indexer(tenant_id)
    document_id = _create_pending_processing_document(tenant_id)

    try:
        result = process_document(
            document_id=document_id,
            tenant_id=tenant_id,
            content=(
                b"Politica institucional sintetica. "
                b"O prazo oficial para resposta e de trinta dias."
            ),
        )

        stored = _processing_state(tenant_id, document_id)
        vectors = _documents_for(real_rag_runtime, tenant_id)
        assert result.status == "ready"
        assert stored.status == "ready"
        assert stored.chunk_count == 1
        assert stored.processed_at is not None
        assert stored.error_message is None
        assert len(vectors) == 1
        assert vectors[0].metadata["document_id"] == document_id
        assert vectors[0].metadata["tenant_id"] == tenant_id
        assert vectors[0].metadata["source_type"] == "document_chunk"
    finally:
        _remove_processing_document(tenant_id, document_id)


def test_process_document_compensates_real_partial_vector_failure(
    monkeypatch,
    real_rag_runtime,
) -> None:
    from app import rag_engine
    from app.document_processing import process_document

    tenant_id = "pr13-processing-failure"
    real_rag_runtime.make_indexer(tenant_id)
    document_id = _create_pending_processing_document(tenant_id)

    def fail_after_first_vector(self, document, chunks, *, previous_chunks=None):
        self.index_document_chunk(document, chunks[0])
        raise RuntimeError("falha sintetica apos vetor parcial")

    monkeypatch.setattr(
        rag_engine.RAGEngine,
        "reindex_document_chunks",
        fail_after_first_vector,
    )

    try:
        result = process_document(
            document_id=document_id,
            tenant_id=tenant_id,
            content=b"Conteudo sintetico para falha vetorial controlada.",
        )

        stored = _processing_state(tenant_id, document_id)
        assert result.status == "error"
        assert stored.status == "error"
        assert stored.chunk_count == 0
        assert stored.chunk_contents == []
        assert stored.error_message == "Falha ao indexar os chunks."
        assert _documents_for(real_rag_runtime, tenant_id) == []
    finally:
        _remove_processing_document(tenant_id, document_id)


def test_delete_document_endpoint_removes_real_record_chunks_and_vectors(
    monkeypatch,
    real_rag_runtime,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "integration-test-secret")

    from app import main
    from app.auth import CurrentUser, get_current_user
    from app.database import SessionLocal
    from app.document_repository import get_document, list_document_chunks

    tenant_id = "pr14-api-delete"
    document_id = _create_ready_document_with_vector(real_rag_runtime, tenant_id)
    monkeypatch.setattr(main, "warm_up_rag_runtime", lambda: None)
    main.app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=tenant_id,
        email="pr14@example.test",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    try:
        assert len(_documents_for(real_rag_runtime, tenant_id)) == 1
        with TestClient(main.app) as client:
            response = client.delete(f"/documents/{document_id}")

        assert response.status_code == 204
        assert response.content == b""
        assert _documents_for(real_rag_runtime, tenant_id) == []

        session = SessionLocal()
        try:
            assert get_document(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            ) is None
            assert list_document_chunks(
                session,
                tenant_id=tenant_id,
                document_id=document_id,
            ) == []
        finally:
            session.close()
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
        _remove_processing_document(tenant_id, document_id)
